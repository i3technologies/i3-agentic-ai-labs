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

import 'dotenv/config';
import express, {
  Request, Response, NextFunction, RequestHandler,
} from 'express';
import { z }              from 'zod';

import { requireAuth, requireRole } from './security/keycloak-auth.js';
import { lobsterTrap }              from './security/lobster-trap.js';
import { assessRole }               from './orchestrator/skills-assessor.js';
import { verifyAll }                from './orchestrator/verify.js';
import { generatePlan, RampUpPlan } from './orchestrator/planner.js';
import { renderMarkdown }           from './render/markdownPlan.js';
import { renderGantt, renderServiceGraph } from './render/graph.js';
import {
  prepareSyncTasks,
  confirmSyncTasks,
  cancelSyncTasks,
  pendingSyncCount,
}                                   from './render/taskSync.js';
import { indexArtifacts, getIndexStats } from './context-store/index.js';
import { ingestPlatform }           from './ingestion/platform.js';
import { chromaHealthy }            from './context-store/chroma-client.js';
import { OnboardingRole }           from './orchestrator/subagents/types.js';

// ──────────────────────────────────────────────────────────────────────────────
// In-memory plan store (keyed by planId).
// Replace with Redis for multi-replica deployments.
// ──────────────────────────────────────────────────────────────────────────────
const planStore = new Map<string, { plan: RampUpPlan; markdown: string; gantt: string }>();

function storePlan(plan: RampUpPlan): string {
  const planId = `${plan.role}-${Date.now()}`;
  planStore.set(planId, {
    plan,
    markdown: renderMarkdown(plan),
    gantt:    renderGantt(plan),
  });
  return planId;
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
// App setup
// ──────────────────────────────────────────────────────────────────────────────

const app  = express();
const PORT = parseInt(process.env.PORT ?? '3000', 10);

app.use(express.json({ limit: '512kb' }));
app.use(express.urlencoded({ extended: false }));

// Request logging (compact)
app.use((req, _res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

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

    console.log(`[plan] Generating ${role} plan for user ${user?.sub ?? 'unknown'}`);

    try {
      // Step 1: Parallel subagent scans
      const assessment    = await assessRole(role);

      // Step 2: Verification pass
      const verifiedScans = await verifyAll(assessment.scanResults);

      // Step 3: Plan synthesis (granite-heavy)
      const plan   = await generatePlan({ role, verifiedScans });
      const planId = storePlan(plan);

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
      res.status(500).json({ error: 'Plan generation failed', detail: (err as Error).message });
    }
  },
);

// ──────────────────────────────────────────────────────────────────────────────
// GET /api/onboarding/plan/:planId
// GET /api/onboarding/plan/:planId/markdown
// GET /api/onboarding/plan/:planId/gantt
// ──────────────────────────────────────────────────────────────────────────────

app.get('/api/onboarding/plan/:planId', requireAuth, (req: Request, res: Response) => {
  const entry = planStore.get(req.params.planId);
  if (!entry) {
    res.status(404).json({ error: 'Plan not found' });
    return;
  }
  res.json(entry.plan);
});

app.get('/api/onboarding/plan/:planId/markdown', requireAuth, (req: Request, res: Response) => {
  const entry = planStore.get(req.params.planId);
  if (!entry) {
    res.status(404).json({ error: 'Plan not found' });
    return;
  }
  res.type('text/markdown').send(entry.markdown);
});

app.get('/api/onboarding/plan/:planId/gantt', requireAuth, (req: Request, res: Response) => {
  const entry = planStore.get(req.params.planId);
  if (!entry) {
    res.status(404).json({ error: 'Plan not found' });
    return;
  }
  res.type('text/plain').send(entry.gantt);
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
  requireAuth,
  lobsterTrapMiddleware,
  (req: Request, res: Response) => {
    const { planId } = req.body as { planId?: string };
    const user       = (req as Request & { user?: { sub: string } }).user;

    if (!planId || !planStore.has(planId)) {
      res.status(404).json({ error: 'Plan not found — generate a plan first' });
      return;
    }

    const { plan }  = planStore.get(planId)!;
    const preview   = prepareSyncTasks(plan, user?.sub ?? 'anonymous');
    res.json(preview);
  },
);

app.post(
  '/api/onboarding/sync/confirm/:pendingId',
  requireAuth,
  async (req: Request, res: Response) => {
    const user = (req as Request & { user?: { sub: string } }).user;
    const result = await confirmSyncTasks(req.params.pendingId, user?.sub ?? 'anonymous');
    res.status(result.success ? 200 : 400).json(result);
  },
);

app.delete(
  '/api/onboarding/sync/:pendingId',
  requireAuth,
  (req: Request, res: Response) => {
    cancelSyncTasks(req.params.pendingId);
    res.json({ cancelled: true });
  },
);

// ──────────────────────────────────────────────────────────────────────────────
// POST /api/onboarding/ingest
// 🔴 admin-only — re-index platform corpus into ChromaDB
// ──────────────────────────────────────────────────────────────────────────────

app.post(
  '/api/onboarding/ingest',
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

  res.json({
    service:      'i3-onboarding-agent',
    chromadb:     chromaStats,
    pendingSyncs: pendingSyncCount(),
    plansCached:  planStore.size,
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

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[server] i3 Onboarding Agent listening on :${PORT}`);
  console.log(`[server] LiteLLM → ${process.env.LITELLM_URL ?? '(not configured)'}`);
  console.log(`[server] ChromaDB → ${process.env.CHROMA_HOST ?? '(not configured)'}:${process.env.CHROMA_PORT ?? '8000'}`);
  console.log(`[server] Keycloak → ${process.env.KEYCLOAK_ISSUER ?? '(not configured)'}`);
});

export default app;
