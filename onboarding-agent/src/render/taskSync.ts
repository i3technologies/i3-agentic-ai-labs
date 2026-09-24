/**
 * taskSync.ts
 * 🟡 ONE-CLICK APPROVAL GATE — sync generated tasks to Directus CRM.
 *
 * Implements the same 2-stage confirmation pattern from
 * platform/admissions/mcp/mcp_connectors.py:
 *   Stage 1: client calls /api/onboarding/sync/prepare → returns pending_id
 *   Stage 2: client calls /api/onboarding/sync/confirm/:pendingId → executes sync
 *
 * Human approval gate levels (matching architecture decisions):
 *   🟢 auto    — plan generation (no sync needed)
 *   🟡 one-click — task sync to CRM (THIS FILE)
 *   🔴 never   — writes to EvalOS or Keycloak (blocked)
 *
 * IMP-06 / STEP-P1-08: All pending-sync state lives in Redis (TTL 300 s).
 * Key schema:  sync:<userId>:<pendingId>  →  JSON(PendingSync)
 * Tenant partition (<userId>) prevents cross-user key collisions under HPA.
 * Redis client is injected via setPendingRedis() called from server.ts.
 * Redis unavailability throws — never falls back to in-memory state.
 */

import { randomUUID } from 'crypto';
import { RampUpPlan, RampUpTask } from '../orchestrator/planner';

const DIRECTUS_URL   = process.env.DIRECTUS_URL   ?? '';
const DIRECTUS_TOKEN = process.env.DIRECTUS_TOKEN ?? '';

const PENDING_TTL_SECONDS = 5 * 60; // 5 minutes

interface PendingSync {
  planId:    string;
  tasks:     RampUpTask[];
  role:      string;
  userId:    string;
  expiresAt: number;  // epoch ms — kept for compatibility; TTL enforced by Redis
}

export interface SyncPreviewResult {
  pendingId:    string;
  taskCount:    number;
  expiresAt:    string;
  previewTasks: Array<{ day: number; title: string; priority: string }>;
}

export interface SyncConfirmResult {
  success:       boolean;
  syncedCount:   number;
  skippedCount:  number;
  directusIds:   string[];
  error?:        string;
}

// ── Redis client (injected from server.ts after connection) ───────────────────
// Avoids a circular-import of the top-level redis instance.
type RedisClient = {
  set(key: string, value: string, options: { EX: number }): Promise<unknown>;
  get(key: string): Promise<string | null>;
  del(key: string): Promise<unknown>;
  keys(pattern: string): Promise<string[]>;
};

let _redis: RedisClient | null = null;

/** Called once from server.ts after the Redis client connects. */
export function setPendingRedis(client: RedisClient): void {
  _redis = client;
}

/** Namespaced key — tenant-partitioned to prevent cross-user collisions under HPA. */
function syncKey(userId: string, pendingId: string): string {
  return `sync:${userId}:${pendingId}`;
}

async function redisPendingSet(userId: string, pendingId: string, entry: PendingSync): Promise<void> {
  if (!_redis) throw new Error('Redis not initialised — call setPendingRedis() first');
  await _redis.set(syncKey(userId, pendingId), JSON.stringify(entry), { EX: PENDING_TTL_SECONDS });
}

async function redisPendingGet(userId: string, pendingId: string): Promise<PendingSync | null> {
  if (!_redis) throw new Error('Redis not initialised — call setPendingRedis() first');
  const raw = await _redis.get(syncKey(userId, pendingId));
  return raw ? (JSON.parse(raw) as PendingSync) : null;
}

async function redisPendingDel(userId: string, pendingId: string): Promise<void> {
  if (!_redis) throw new Error('Redis not initialised — call setPendingRedis() first');
  await _redis.del(syncKey(userId, pendingId));
}

// ──────────────────────────────────────────────────────────────────────────────
// Stage 1: Prepare (returns pending_id for client to confirm)
// ──────────────────────────────────────────────────────────────────────────────

export async function prepareSyncTasks(
  plan:   RampUpPlan,
  userId: string,
): Promise<SyncPreviewResult> {
  const now       = Date.now();
  const pendingId = randomUUID();
  const expiresAt = now + PENDING_TTL_SECONDS * 1_000;

  await redisPendingSet(userId, pendingId, {
    planId:    `${plan.role}-${plan.generatedAt}`,
    tasks:     plan.tasks,
    role:      plan.role,
    userId,
    expiresAt,
  });

  return {
    pendingId,
    taskCount:  plan.tasks.length,
    expiresAt:  new Date(expiresAt).toISOString(),
    previewTasks: plan.tasks.slice(0, 5).map(t => ({
      day:      t.day,
      title:    t.title,
      priority: t.priority,
    })),
  };
}

// ──────────────────────────────────────────────────────────────────────────────
// Stage 2: Confirm (executes the actual sync after user clicks confirm)
// ──────────────────────────────────────────────────────────────────────────────

export async function confirmSyncTasks(
  pendingId: string,
  userId:    string,
): Promise<SyncConfirmResult> {
  const entry = await redisPendingGet(userId, pendingId);

  if (!entry) {
    return {
      success:      false,
      syncedCount:  0,
      skippedCount: 0,
      directusIds:  [],
      error:        'Pending sync not found or expired. Please generate a new plan.',
    };
  }

  if (entry.userId !== userId) {
    return {
      success:      false,
      syncedCount:  0,
      skippedCount: 0,
      directusIds:  [],
      error:        'User mismatch — confirmation must come from the same user.',
    };
  }

  // Consume the token immediately (delete before executing to prevent double-fire)
  await redisPendingDel(userId, pendingId);

  if (!DIRECTUS_URL || !DIRECTUS_TOKEN) {
    console.warn('[taskSync] DIRECTUS_URL or DIRECTUS_TOKEN not set — skipping CRM sync');
    return {
      success:      true,
      syncedCount:  0,
      skippedCount: entry.tasks.length,
      directusIds:  [],
      error:        'Directus not configured — tasks not synced to CRM',
    };
  }

  const directusIds: string[] = [];
  let   synced  = 0;
  let   skipped = 0;

  for (const task of entry.tasks) {
    try {
      const resp = await fetch(`${DIRECTUS_URL}/items/onboarding_tasks`, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${DIRECTUS_TOKEN}`,
        },
        body: JSON.stringify({
          role:              entry.role,
          user_id:           userId,
          day:               task.day,
          title:             task.title,
          description:       task.description,
          file_paths:        task.filePaths.join('\n'),
          verified:          task.verified,
          priority:          task.priority,
          estimated_hours:   task.estimatedHours,
          historical_ref:    task.historicalIssueRef ?? null,
          confidence:        task.confidence,
          created_at:        new Date().toISOString(),
        }),
      });

      if (resp.ok) {
        const body = await resp.json() as { data?: { id: string } };
        directusIds.push(body.data?.id ?? 'unknown');
        synced++;
      } else {
        console.warn(`[taskSync] Directus returned ${resp.status} for task: ${task.title}`);
        skipped++;
      }
    } catch (err) {
      console.warn(`[taskSync] Failed to sync task: ${task.title}`, (err as Error).message);
      skipped++;
    }
  }

  return {
    success:      true,
    syncedCount:  synced,
    skippedCount: skipped,
    directusIds,
  };
}

/**
 * Cancel a pending sync (e.g. user clicked "Dismiss").
 * userId is required to resolve the tenant-partitioned key.
 */
export async function cancelSyncTasks(pendingId: string, userId: string): Promise<void> {
  await redisPendingDel(userId, pendingId);
}

/** How many pending syncs are awaiting confirmation (for health endpoint). */
export async function pendingSyncCount(): Promise<number> {
  if (!_redis) return 0;
  const keys = await _redis.keys('sync:*');
  return keys.length;
}
