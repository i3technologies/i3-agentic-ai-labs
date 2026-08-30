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
 */

import { randomUUID } from 'crypto';
import { RampUpPlan, RampUpTask } from '../orchestrator/planner';

const DIRECTUS_URL   = process.env.DIRECTUS_URL   ?? '';
const DIRECTUS_TOKEN = process.env.DIRECTUS_TOKEN ?? '';

// In-memory pending store (same pattern as mcp_connectors.py _pending dict).
// NOTE: replace with Redis for multi-replica production deployment.
interface PendingSync {
  planId:    string;
  tasks:     RampUpTask[];
  role:      string;
  userId:    string;
  expiresAt: number;  // epoch ms
}

const _pending = new Map<string, PendingSync>();
const PENDING_TTL_MS = 5 * 60 * 1_000; // 5 minutes

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

// ──────────────────────────────────────────────────────────────────────────────
// Stage 1: Prepare (returns pending_id for client to confirm)
// ──────────────────────────────────────────────────────────────────────────────

export function prepareSyncTasks(
  plan:   RampUpPlan,
  userId: string,
): SyncPreviewResult {
  // Purge expired entries
  const now = Date.now();
  for (const [id, entry] of _pending) {
    if (entry.expiresAt < now) _pending.delete(id);
  }

  const pendingId = randomUUID();
  const expiresAt = now + PENDING_TTL_MS;

  _pending.set(pendingId, {
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
  const entry = _pending.get(pendingId);

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

  if (entry.expiresAt < Date.now()) {
    _pending.delete(pendingId);
    return {
      success:      false,
      syncedCount:  0,
      skippedCount: 0,
      directusIds:  [],
      error:        'Pending sync has expired. Please generate a new plan.',
    };
  }

  _pending.delete(pendingId);

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

/** Cancel a pending sync (e.g. user clicked "Dismiss"). */
export function cancelSyncTasks(pendingId: string): void {
  _pending.delete(pendingId);
}

/** How many pending syncs are awaiting confirmation (for health endpoint). */
export function pendingSyncCount(): number {
  const now = Date.now();
  let count = 0;
  for (const entry of _pending.values()) {
    if (entry.expiresAt >= now) count++;
  }
  return count;
}
