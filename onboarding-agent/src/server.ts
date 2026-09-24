/**
 * server.ts
 * Express entrypoint for the i3 Onboarding Agent.
 * Namespace: i3-onboarding · Port: 3000
 *
 * Middleware chain (all protected endpoints):
 *   1. Lobster Trap firewall  — blocks prompt injection on all user-supplied text
 *   2. Keycloak auth          — validates Bearer JWT from sso.i3technologies.co.ke/realms/i3
 *   3. Route handlers         — plan generation, sync, ingest, health
 *
 * Route summary:
 *   GET  /health                              → liveness probe (no auth)
 *   GET  /ready                               → readiness probe (no auth)
 *   POST /api/onboarding/plan                 → 🟢 auto — generate ramp-up plan
 *   GET  /api/onboarding/plan/:planId         → 🟢 auto — retrieve stored plan JSON
 *   GET  /api/onboarding/plan/:planId/markdown → 🟢 auto — Markdown render
 *   POST /api/onboarding/sync/prepare         → 🟡 one-click — stage-1 CRM sync
 *   POST /api/onboarding/sync/confirm/:id     → 🟡 one-click — stage-2 CRM sync
 *   DELETE /api/onboarding/sync/:id           → cancel pending sync
 *   POST /api/onboarding/ingest               → 🔴 admin only — re-index corpus
 *   GET  /api/onboarding/status               → ChromaDB + pending sync stats
 */

import './tracing';   // OTel SDK — must be first import (STEP-P1-14)
import 'dotenv/config';
import express, {
  Request, Response, NextFunction, RequestHandler,
} from 'express';
import { createClient }   from 'redis';
import { createHmac, timingSafeEqual } from 'crypto';
import { z }              from 'zod';

import { requireAuth, requireRole } from './security/keycloak-auth';
import { lobsterTrap }              from './security/lobster-trap';
import { assessRole }               from './orchestrator/skills-assessor';
import { verifyAll }                from './orchestrator/verify';
import { generatePlan, RampUpPlan } from './orchestrator/planner';
import { renderMarkdown }           from './render/markdownPlan';
import { renderGantt, renderServiceGraph } from './render/graph';
import {
  prepareSyncTasks,
  confirmSyncTasks,
  cancelSyncTasks,
  pendingSyncCount,
  setPendingRedis,
}                                   from './render/taskSync';
import { indexArtifacts, getIndexStats } from './context-store/index';
import { ingestPlatform }           from './ingestion/platform';
import { chromaHealthy }            from './context-store/chroma-client';
import { OnboardingRole }           from './orchestrator/subagents/types';

// ──────────────────────────────────────────────────────────────────────────────
// Redis plan store.
// IMP-06: Keys are tenant-partitioned: plan:<ownerSub>:<planId>
//         Prevents cross-user key visibility under HPA-scaled replicas.
// TTL: 7200 s.  REDIS_URL is resolved from the environment (OpenBao i3/redis/url).
// On connection failure all plan operations return HTTP 503 — no in-memory fallback.
// ──────────────────────────────────────────────────────────────────────────────

// FINDING-OA-4: PlanEntry carries ownerSub so GET endpoints can verify
// the requesting user is the same user who generated the plan.
type PlanEntry = { plan: RampUpPlan; markdown: string; gantt: string; ownerSub: string };

const redis = createClient({ url: process.env.REDIS_URL ?? 'redis://localhost:6379' });

redis.on('error', (err: Error) => console.error('[redis] client error:', err.message));

/** Tenant-partitioned Redis key for plan storage. */
function planKey(ownerSub: string, planId: string): string {
  return `plan:${ownerSub}:${planId}`;
}

async function storePlan(plan: RampUpPlan, ownerSub: string): Promise<string> {
  // FINDING-OA-4: use a cryptographically random suffix instead of timestamp.
  const randomSuffix = Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10);
  const planId = `${plan.role}-${randomSuffix}`;
  const entry: PlanEntry = {
    plan,
    markdown: renderMarkdown(plan),
    gantt:    renderGantt(plan),
    ownerSub,
  };
  await redis.set(planKey(ownerSub, planId), JSON.stringify(entry), { EX: 7200 });
  return planId;
}

async function getPlanEntry(planId: string, callerSub: string): Promise<PlanEntry | null> {
  const raw = await redis.get(planKey(callerSub, planId));
  if (!raw) return null;
  return JSON.parse(raw) as PlanEntry;
}

async function hasPlan(planId: string, ownerSub: string): Promise<boolean> {
  return (await redis.exists(planKey(ownerSub, planId))) === 1;
}

async function deletePlan(planId: string, ownerSub: string): Promise<void> {
  await redis.del(planKey(ownerSub, planId));
}

// ──────────────────────────────────────────────────────────────────────────────
// Lobster Trap middleware wrapper for Express
// ──────────────────────────────────────────────────────────────────────────────
const lobsterTrapMiddleware: RequestHandler = (req, res, next) => {
  // Only inspect text bodies — skip binary / multipart
  const body    = req.body as Record<string, unknown> | undefined;
  const suspect = [
    body?.role,
    body?.context,
    body?.query,
    body?.note,
  ]
    .filter(Boolean)
    .map(String);

  for (const text of suspect) {
    const matched = lobsterTrap(text);   // returns matched pattern string or null
    if (matched !== null) {
      res.status(400).json({
        error:   'Request blocked by security policy',
        pattern: matched,
      });
      return;
    }
  }
  next();
};

// ──────────────────────────────────────────────────────────────────────────────
// Schema validation helpers
// ──────────────────────────────────────────────────────────────────────────────

const VALID_ROLES: OnboardingRole[] = [
  'bootcamp_student',
  'platform_engineer',
  'ai_ml_engineer',
  'backend_engineer',
  'security_engineer',
];

const GeneratePlanBody = z.object({
  role: z.enum([
    'bootcamp_student',
    'platform_engineer',
    'ai_ml_engineer',
    'backend_engineer',
    'security_engineer',
  ]),
  note: z.string().max(500).optional(),  // optional context note from the requester
});

// ──────────────────────────────────────────────────────────────────────────────
// HMAC-SHA256 webhook signature validation
// Validates X-Hub-Signature-256 (format: "sha256=<hex>") against the raw
// request body using a constant-time comparison (timingSafeEqual).
// Set ONBOARDING_WEBHOOK_SECRET to the shared secret configured in the caller
// (e.g. the n8n webhook node or an external orchestrator).
// Attach as middleware to any route that accepts external trigger webhooks.
// ──────────────────────────────────────────────────────────────────────────────

const ONBOARDING_WEBHOOK_SECRET = process.env.ONBOARDING_WEBHOOK_SECRET ?? '';

/**
 * Express middleware that captures the raw request body for HMAC verification.
 * Must be registered BEFORE express.json() parses the body.
 * Stores the raw Buffer on req as (req as RawBodyRequest).rawBody.
 */
interface RawBodyRequest extends Request {
  rawBody?: Buffer;
}

const captureRawBody = (
  req: RawBodyRequest,
  _res: Response,
  buf: Buffer,
): void => {
  req.rawBody = buf;
};

/**
 * Validates the X-Hub-Signature-256 header on inbound trigger webhooks.
 * Returns 401 immediately when the header is present but the HMAC is invalid
 * or when ONBOARDING_WEBHOOK_SECRET is not configured.
 * Requests without the header pass through (they rely on Keycloak auth).
 */
const validateWebhookSignature: RequestHandler = (req, res, next) => {
  const sigHeader = req.headers['x-hub-signature-256'];
  if (!sigHeader) {
    next();
    return;
  }

  // Header present → full HMAC validation required.
  if (!ONBOARDING_WEBHOOK_SECRET) {
    console.error('[webhook] ONBOARDING_WEBHOOK_SECRET is not set — rejecting signed request');
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }

  const sig = Array.isArray(sigHeader) ? sigHeader[0] : sigHeader;
  if (!sig.startsWith('sha256=')) {
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }

  const rawBody = (req as RawBodyRequest).rawBody;
  if (!rawBody) {
    // Should never happen if captureRawBody verify callback is wired in.
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }

  const expected    = `sha256=${createHmac('sha256', ONBOARDING_WEBHOOK_SECRET).update(rawBody).digest('hex')}`;
  const sigBuf      = Buffer.from(sig,      'utf8');
  const expectedBuf = Buffer.from(expected, 'utf8');

  if (sigBuf.length !== expectedBuf.length || !timingSafeEqual(sigBuf, expectedBuf)) {
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }

  next();
};

// ──────────────────────────────────────────────────────────────────────────────
// App setup
// ──────────────────────────────────────────────────────────────────────────────

const app  = express();
const PORT = parseInt(process.env.PORT ?? '3000', 10);

// Register raw-body capture via the verify callback BEFORE json() parses the
// body.  This is the only Express-native way to access the raw bytes needed for
// HMAC signature verification without a separate body-reading pass.
app.use(express.json({
  limit: '512kb',
  verify: captureRawBody as unknown as (req: Request, res: Response, buf: Buffer) => void,
}));
app.use(express.urlencoded({ extended: false }));

// Request logging (compact)
app.use((req, _res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// Helper: translate Redis disconnection into HTTP 503
function isRedisDown(err: unknown): boolean {
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    return msg.includes('econnrefused') || msg.includes('socket') || msg.includes('disconnected');
  }
  return false;
}

// ──────────────────────────────────────────────────────────────────────────────
// Probes (no auth required — OpenShift liveness/readiness)
// ──────────────────────────────────────────────────────────────────────────────

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'i3-onboarding-agent' });
});

app.get('/ready', async (_req, res) => {
  const chromaOk = await chromaHealthy();
  const status   = chromaOk ? 200 : 503;
  res.status(status).json({
    status:  chromaOk ? 'ready' : 'not-ready',
    chromadb: chromaOk,
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// POST /api/onboarding/plan
// 🟢 auto approval — generate a ramp-up plan
// ──────────────────────────────────────────────────────────────────────────────

app.post(
  '/api/onboarding/plan',
  validateWebhookSignature,
  requireAuth,
  lobsterTrapMiddleware,
  async (req: Request, res: Response) => {
    const parsed = GeneratePlanBody.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation failed', issues: parsed.error.issues });
      return;
    }

    const { role } = parsed.data;
    const user     = (req as Request & { user?: { sub: string } }).user;
    const sessionId = `plan-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    console.log(`[plan] Generating ${role} plan for user ${user?.sub ?? 'unknown'}`);

    try {
      // Step 1: Parallel subagent scans
      const assessment    = await assessRole(role, sessionId);

      // Step 2: Verification pass
      const verifiedScans = await verifyAll(assessment.scanResults);

      // Step 3: Plan synthesis (granite-heavy)
      const plan      = await generatePlan({ role, verifiedScans, sessionId });
      const ownerSub  = user?.sub ?? 'anonymous';
      const planId    = await storePlan(plan, ownerSub);

      res.status(200).json({
        planId,
        role,
        totalTasks:      plan.tasks.length,
        totalVerified:   plan.totalVerified,
        totalUnverified: plan.totalUnverified,
        staleDocWarnings: plan.staleDocWarnings,
        plan,
      });
    } catch (err) {
      console.error('[plan] Generation error:', err);
      if (isRedisDown(err)) {
        res.status(503).json({ error: 'Plan store unavailable — Redis connection error' });
      } else {
        res.status(500).json({ error: 'Plan generation failed', detail: (err as Error).message });
      }
    }
  },
);

// ──────────────────────────────────────────────────────────────────────────────
// GET /api/onboarding/plan/:planId
// GET /api/onboarding/plan/:planId/markdown
// GET /api/onboarding/plan/:planId/gantt
// ──────────────────────────────────────────────────────────────────────────────

app.get('/api/onboarding/plan/:planId', requireAuth, async (req: Request, res: Response) => {
  const callerSub = (req as Request & { user?: { sub: string } }).user?.sub ?? '';
  try {
    const entry = await getPlanEntry(req.params.planId, callerSub);
    if (!entry) {
      res.status(404).json({ error: 'Plan not found' });
      return;
    }
    res.json(entry.plan);
  } catch (err) {
    if (isRedisDown(err)) res.status(503).json({ error: 'Plan store unavailable' });
    else res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/onboarding/plan/:planId/markdown', requireAuth, async (req: Request, res: Response) => {
  const callerSub = (req as Request & { user?: { sub: string } }).user?.sub ?? '';
  try {
    const entry = await getPlanEntry(req.params.planId, callerSub);
    if (!entry) {
      res.status(404).json({ error: 'Plan not found' });
      return;
    }
    res.type('text/markdown').send(entry.markdown);
  } catch (err) {
    if (isRedisDown(err)) res.status(503).json({ error: 'Plan store unavailable' });
    else res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/onboarding/plan/:planId/gantt', requireAuth, async (req: Request, res: Response) => {
  const callerSub = (req as Request & { user?: { sub: string } }).user?.sub ?? '';
  try {
    const entry = await getPlanEntry(req.params.planId, callerSub);
    if (!entry) {
      res.status(404).json({ error: 'Plan not found' });
      return;
    }
    res.type('text/plain').send(entry.gantt);
  } catch (err) {
    if (isRedisDown(err)) res.status(503).json({ error: 'Plan store unavailable' });
    else res.status(500).json({ error: 'Internal server error' });
  }
});

// ──────────────────────────────────────────────────────────────────────────────
// GET /api/onboarding/graph — static service topology diagram
// ──────────────────────────────────────────────────────────────────────────────

app.get('/api/onboarding/graph', requireAuth, (_req, res) => {
  res.type('text/plain').send(renderServiceGraph());
});

// ──────────────────────────────────────────────────────────────────────────────
// POST /api/onboarding/sync/prepare       🟡 one-click stage 1
// POST /api/onboarding/sync/confirm/:id   🟡 one-click stage 2
// DELETE /api/onboarding/sync/:id         cancel
// ──────────────────────────────────────────────────────────────────────────────

app.post(
  '/api/onboarding/sync/prepare',
  validateWebhookSignature,
  requireAuth,
  lobsterTrapMiddleware,
  async (req: Request, res: Response) => {
    const { planId } = req.body as { planId?: string };
    const user       = (req as Request & { user?: { sub: string } }).user;

    if (!planId) {
      res.status(404).json({ error: 'Plan not found — generate a plan first' });
      return;
    }

    try {
      const entry = await getPlanEntry(planId, user?.sub ?? 'anonymous');
      if (!entry) {
        res.status(404).json({ error: 'Plan not found — generate a plan first' });
        return;
      }
      const preview = await prepareSyncTasks(entry.plan, user?.sub ?? 'anonymous');
      res.json(preview);
    } catch (err) {
      if (isRedisDown(err)) res.status(503).json({ error: 'Plan store unavailable' });
      else res.status(500).json({ error: 'Internal server error' });
    }
  },
);

app.post(
  '/api/onboarding/sync/confirm/:pendingId',
  validateWebhookSignature,
  requireAuth,
  async (req: Request, res: Response) => {
    const user = (req as Request & { user?: { sub: string } }).user;
    try {
      const result = await confirmSyncTasks(req.params.pendingId, user?.sub ?? 'anonymous');
      res.status(result.success ? 200 : 400).json(result);
    } catch (err) {
      if (isRedisDown(err)) res.status(503).json({ error: 'Plan store unavailable — Redis connection error' });
      else res.status(500).json({ error: 'Internal server error' });
    }
  },
);

app.delete(
  '/api/onboarding/sync/:pendingId',
  requireAuth,
  async (req: Request, res: Response) => {
    const user = (req as Request & { user?: { sub: string } }).user;
    try {
      await cancelSyncTasks(req.params.pendingId, user?.sub ?? 'anonymous');
      res.json({ cancelled: true });
    } catch (err) {
      if (isRedisDown(err)) res.status(503).json({ error: 'Plan store unavailable — Redis connection error' });
      else res.status(500).json({ error: 'Internal server error' });
    }
  },
);

// ──────────────────────────────────────────────────────────────────────────────
// POST /api/onboarding/ingest
// 🔴 admin-only — re-index platform corpus into ChromaDB
// ──────────────────────────────────────────────────────────────────────────────

app.post(
  '/api/onboarding/ingest',
  validateWebhookSignature,
  requireAuth,
  requireRole('i3-admin'),
  async (_req, res: Response) => {
    try {
      const platformPath = process.env.PLATFORM_REPO_PATH ?? '../platform';
      console.log(`[ingest] Starting platform corpus ingest from ${platformPath}`);

      const artifacts = await ingestPlatform(platformPath);
      const result    = await indexArtifacts(artifacts, { verbose: true });

      res.json({
        status:    'ok',
        ...result,
      });
    } catch (err) {
      console.error('[ingest] Error:', err);
      res.status(500).json({ error: 'Ingest failed', detail: (err as Error).message });
    }
  },
);

// ──────────────────────────────────────────────────────────────────────────────
// GET /api/onboarding/status
// ──────────────────────────────────────────────────────────────────────────────

app.get('/api/onboarding/status', requireAuth, async (_req, res: Response) => {
  const [chromaStats, chromaOk] = await Promise.all([
    getIndexStats(),
    chromaHealthy(),
  ]);

  // plansCached reports the count of keys matching plan:* — best-effort, 0 on Redis failure
  let plansCached = 0;
  try {
    const keys = await redis.keys('plan:*:*');
    plansCached = keys.length;
  } catch {
    // non-fatal — Redis may be briefly unavailable
  }

  res.json({
    service:      'i3-onboarding-agent',
    chromadb:     chromaStats,
    pendingSyncs: await pendingSyncCount(),
    plansCached,
    validRoles:   VALID_ROLES,
    models: {
      fast:  process.env.LITELLM_MODEL_FAST  ?? 'granite-nano',
      scan:  process.env.LITELLM_MODEL_SCAN  ?? 'mistral-nemo',
      synth: process.env.LITELLM_MODEL_SYNTH ?? 'granite-heavy',
    },
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Global error handler
// ──────────────────────────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-unused-vars
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('[server] Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// ──────────────────────────────────────────────────────────────────────────────
// Start
// ──────────────────────────────────────────────────────────────────────────────

redis.connect().then(() => {
  console.log(`[redis] connected to ${process.env.REDIS_URL ?? 'redis://localhost:6379'}`);
  // Wire the shared Redis client into taskSync for pending-sync state (STEP-P1-08)
  setPendingRedis(redis);
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[server] i3 Onboarding Agent listening on :${PORT}`);
    console.log(`[server] LiteLLM → ${process.env.LITELLM_URL ?? '(not configured)'}`);
    console.log(`[server] ChromaDB → ${process.env.CHROMA_HOST ?? '(not configured)'}:${process.env.CHROMA_PORT ?? '8000'}`);
    console.log(`[server] Keycloak → ${process.env.KEYCLOAK_ISSUER ?? '(not configured)'}`);
    console.log(`[server] Redis    → ${process.env.REDIS_URL ?? 'redis://localhost:6379'}`);
  });
}).catch((err: Error) => {
  console.error('[redis] failed to connect on startup:', err.message);
  process.exit(1);
});

export default app;
