/**
 * mock-litellm.mjs
 * Minimal OpenAI-compatible mock server for local laptop testing.
 * Responds to:
 *   POST /v1/chat/completions  → returns a canned JSON plan/findings response
 *   GET  /v1/models            → returns model list
 *   GET  /health               → liveness
 *
 * Run:  node scripts/mock-litellm.mjs
 * Port: 4000
 */

import http from 'http';

const PORT = 4000;

// ── Canned subagent findings response (used for mistral-nemo scan calls) ──
const MOCK_FINDINGS = {
  findings: [
    {
      title: 'Read the RUNBOOK.md — OpenBao bootstrap and DR procedures',
      description:
        'platform/RUNBOOK.md is the single most important Day-1 document. ' +
        'It covers the OpenBao unseal procedure, DR restore steps, and the ' +
        'FORBIDDEN solution-01..08 namespace rule.',
      filePaths: ['RUNBOOK.md'],
      priority: 'high',
      suggestedDay: 1,
      roles: ['platform_engineer'],
      historicalIssueRef: null,
    },
    {
      title: 'Explore ArgoCD app-of-apps.yaml — 6-wave GitOps structure',
      description:
        'platform/gitops/argocd/app-of-apps.yaml defines 7 ArgoCD waves. ' +
        'Wave 7 is the onboarding agent itself. Understand wave ordering before ' +
        'making any GitOps changes.',
      filePaths: ['gitops/argocd/app-of-apps.yaml'],
      priority: 'high',
      suggestedDay: 1,
      roles: ['platform_engineer'],
      historicalIssueRef: null,
    },
    {
      title: 'Install project-specific developer tools (Makefile targets)',
      description:
        'Run `make help` from the repo root to see all available targets. ' +
        'Required tools: oc, argocd, tekton, bao (OpenBao), Node.js 20, buildah. ' +
        'See platform/RUNBOOK.md §Developer Setup.',
      filePaths: ['Makefile', 'RUNBOOK.md'],
      priority: 'high',
      suggestedDay: 1,
      roles: ['platform_engineer', 'ai_ml_engineer', 'backend_engineer'],
      historicalIssueRef: null,
    },
    {
      title: 'Needs verification: Explore RHOAI AI Lab Namespace (referenced path not found — likely stale doc)',
      description:
        'platform/docs/platform-documentation.md states RHOAI (i3-ai-lab namespace) ' +
        'is available from Month 3. The live cluster check confirms the namespace ' +
        'does not yet exist. Do not build dependencies on this namespace.',
      filePaths: ['docs/platform-documentation.md'],
      priority: 'high',
      suggestedDay: 2,
      roles: ['ai_ml_engineer', 'platform_engineer'],
      historicalIssueRef: 'stale-doc: RHOAI namespace availability (Month 3)',
    },
    {
      title: 'Study the Tekton pipeline i3-build-deploy',
      description:
        'platform/gitops/tekton/pipeline-build.yaml defines git-clone → buildah → ' +
        'trivy → rolling-update. Understand each task before triggering a build.',
      filePaths: ['gitops/tekton/pipeline-build.yaml'],
      priority: 'medium',
      suggestedDay: 2,
      roles: ['platform_engineer'],
      historicalIssueRef: null,
    },
  ],
};

// ── Canned plan synthesis response (used for granite-heavy synth calls) ──
const MOCK_PLAN_TASKS = {
  tasks: [
    {
      day: 1,
      title: 'Install project-specific developer tools',
      description:
        'Run `make help` to list all Makefile targets. Install required CLIs: ' +
        'oc, argocd, tekton, bao, Node.js 20, buildah. See platform/RUNBOOK.md §Developer Setup.',
      filePaths: ['Makefile', 'RUNBOOK.md'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'high',
      estimatedHours: 2,
      historicalIssueRef: null,
      roles: ['platform_engineer'],
      confidence: 0.97,
    },
    {
      day: 1,
      title: 'Read RUNBOOK.md — OpenBao, forbidden namespaces, DR',
      description:
        'platform/RUNBOOK.md covers the full Day-2 ops guide. ' +
        'Critical: solution-01 through solution-08 namespaces are FORBIDDEN — ' +
        'never modify them. Note the OpenBao unseal procedure.',
      filePaths: ['RUNBOOK.md'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'high',
      estimatedHours: 3,
      historicalIssueRef: 'closed-issue #42: accidental solution-03 namespace modification',
      roles: ['platform_engineer'],
      confidence: 0.95,
    },
    {
      day: 1,
      title: 'Needs verification: Explore RHOAI AI Lab Namespace (referenced path not found — likely stale doc)',
      description:
        'platform/docs/platform-documentation.md states RHOAI (i3-ai-lab) is "available from Month 3". ' +
        'Live ROKS cluster check confirms the namespace does NOT yet exist. ' +
        'Any tasks referencing i3-ai-lab are blocked until Month 3.',
      filePaths: ['docs/platform-documentation.md'],
      verified: false,
      verificationNote: 'RHOAI/i3-ai-lab namespace not live — platform-documentation.md states "available from Month 3"',
      priority: 'high',
      estimatedHours: 1,
      historicalIssueRef: 'stale-doc: RHOAI namespace availability',
      roles: ['ai_ml_engineer', 'platform_engineer'],
      confidence: 0.91,
    },
    {
      day: 2,
      title: 'Explore ArgoCD app-of-apps.yaml — wave 7 onboarding',
      description:
        'platform/gitops/argocd/app-of-apps.yaml now has 7 waves. Wave 7 is the onboarding agent. ' +
        'Understand wave ordering: core-operators → model-gateway → ai-lab → evalos → ott → admissions → onboarding.',
      filePaths: ['gitops/argocd/app-of-apps.yaml'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'high',
      estimatedHours: 2,
      historicalIssueRef: null,
      roles: ['platform_engineer'],
      confidence: 0.93,
    },
    {
      day: 2,
      title: 'Study Tekton pipeline i3-build-deploy',
      description:
        'platform/gitops/tekton/pipeline-build.yaml: git-clone → buildah → trivy → rolling-update. ' +
        'Run `make build-onboarding` to trigger a build for the onboarding agent.',
      filePaths: ['gitops/tekton/pipeline-build.yaml'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'medium',
      estimatedHours: 2,
      historicalIssueRef: null,
      roles: ['platform_engineer'],
      confidence: 0.88,
    },
    {
      day: 3,
      title: 'Review admissions_agent.py — FastAPI + Lobster Trap pattern',
      description:
        'platform/admissions/admissions_agent.py is the reference implementation for all i3 agents. ' +
        'Study: SSE streaming endpoint, Lobster Trap firewall (12 patterns), 0.65 confidence gate, ' +
        'MCP connector calls.',
      filePaths: ['admissions/admissions_agent.py'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'high',
      estimatedHours: 3,
      historicalIssueRef: null,
      roles: ['ai_ml_engineer', 'backend_engineer'],
      confidence: 0.92,
    },
    {
      day: 3,
      title: 'Run the RAGAS evaluation suite',
      description:
        'platform/testing/testing.py --ragas-onboarding evaluates plan quality. ' +
        'Targets: Faithfulness ≥ 0.80, Answer Relevancy ≥ 0.75. ' +
        'Run via: make test-onboarding',
      filePaths: ['testing/testing.py'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'medium',
      estimatedHours: 2,
      historicalIssueRef: null,
      roles: ['ai_ml_engineer'],
      confidence: 0.85,
    },
    {
      day: 4,
      title: 'Review EvalOS schema and exam engine',
      description:
        'platform/evalos/schema.sql: questions, exams, quiz_attempts, enrolment_queue, ai_interviews tables. ' +
        'platform/evalos/nextjs/exam-engine.ts: anti-cheat event recording, Bloom taxonomy difficulty levels.',
      filePaths: ['evalos/schema.sql'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'medium',
      estimatedHours: 3,
      historicalIssueRef: null,
      roles: ['bootcamp_student', 'backend_engineer'],
      confidence: 0.87,
    },
    {
      day: 5,
      title: 'Make your first independent contribution',
      description:
        'Pick an open issue from the platform repo. Create a branch, make the change, open a PR. ' +
        'Ensure Tekton pipeline passes (trivy + build) before requesting review.',
      filePaths: ['Makefile'],
      verified: true,
      verificationNote: 'all referenced paths confirmed present',
      priority: 'low',
      estimatedHours: 4,
      historicalIssueRef: null,
      roles: ['platform_engineer', 'ai_ml_engineer', 'backend_engineer'],
      confidence: 0.80,
    },
  ],
};

// ── HTTP server ──────────────────────────────────────────────────────────────

const server = http.createServer((req, res) => {
  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', () => {
    const url = req.url ?? '';

    // GET /health
    if (req.method === 'GET' && url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', service: 'mock-litellm' }));
      return;
    }

    // GET /v1/models
    if (req.method === 'GET' && url === '/v1/models') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        object: 'list',
        data: [
          { id: 'granite-nano',  object: 'model' },
          { id: 'mistral-nemo',  object: 'model' },
          { id: 'granite-heavy', object: 'model' },
        ],
      }));
      return;
    }

    // POST /v1/chat/completions
    if (req.method === 'POST' && url === '/v1/chat/completions') {
      let parsed = {};
      try { parsed = JSON.parse(body); } catch {}
      const model = parsed.model ?? 'unknown';

      // Choose canned response based on model tier
      const issynth = model === 'granite-heavy';
      const payload  = issynth ? MOCK_PLAN_TASKS : MOCK_FINDINGS;

      const response = {
        id:      `mock-${Date.now()}`,
        object:  'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model,
        choices: [{
          index:         0,
          message: {
            role:    'assistant',
            content: JSON.stringify(payload),
          },
          finish_reason: 'stop',
        }],
        usage: { prompt_tokens: 100, completion_tokens: 200, total_tokens: 300 },
      };

      console.log(`[mock-litellm] ${model} → ${issynth ? 'plan-synthesis' : 'findings'} response`);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(response));
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'not found', url }));
  });
});

server.listen(PORT, () => {
  console.log(`[mock-litellm] listening on http://localhost:${PORT}`);
  console.log(`[mock-litellm] models: granite-nano (Tier3), mistral-nemo (Tier2), granite-heavy (Tier1)`);
  console.log(`[mock-litellm] POST /v1/chat/completions → canned findings/plan responses`);
});
