# i3 Onboarding Agent

> **IBM TechXchange Hackathon 2026 · Aug 28–30 · Project 1: Codebase Onboarding Agent**  
> Built by i3 Agentic AI Labs — deployed on IBM ROKS 4.15, Frankfurt (eu-de)

---

## What Is This?

The **i3 Onboarding Agent** is a production-grade AI service that reads your real codebase and generates a **verified, role-specific, 5-day ramp-up plan** for any new team member — in a single API call.

You send it a role (`platform_engineer`, `ai_ml_engineer`, `bootcamp_student`, `backend_engineer`, `security_engineer`). It fires **three AI subagents in parallel** to analyse different parts of the codebase, checks that every file path it references **actually exists** in the repository, catches stale documentation automatically, and returns a structured JSON plan with a Markdown document and Mermaid Gantt chart.

### The Key Demo Moment

`platform/docs/platform-documentation.md` states the RHOAI namespace (`i3-ai-lab`) is *"available from Month 3"*. The agent calls the **live Kubernetes API**, confirms the namespace does not yet exist, and automatically flags that task as `verified: false` with the prefix:

> `"Needs verification: [title] (referenced path not found — likely stale doc)"`

This is live, automated stale-documentation detection — not a simulation.

---

## Architecture

```
POST /api/onboarding/plan  { "role": "platform_engineer" }
         │
         ▼
[1] Lobster Trap Firewall    ← 12 regex patterns block prompt injection
         │
[2] Keycloak JWT Auth        ← RS256 validation against sso.i3technologies.co.ke
         │
[3] Skills Assessor          ← maps role → 3 subagents
    ├── infra-scan    ─────────┐
    ├── ailab-scan    ─────────┤  ← ALL 3 run in parallel (Promise.all)
    └── backend-scan  ─────────┘
         │  each:  ChromaDB RAG context → mistral-nemo (Tier 2) → findings[]
         │
[4] Verify Pass              ← existsSync() on every filePath
    └── RHOAI namespace live-check via Kubernetes API
         │  → verified: false + stale-doc prefix on failures
         │
[5] Plan Synthesis           ← granite-heavy (Tier 1), confidence gate 0.65
         │
[6] Response                 ← RampUpPlan JSON + planId
         │
    GET /plan/:id/markdown   ← Markdown with priority badges
    GET /plan/:id/gantt      ← Mermaid Gantt chart
    POST /sync/prepare       ← 🟡 Stage-1 CRM sync (one-click gate)
    POST /sync/confirm/:id   ← 🟡 Stage-2 CRM sync → Directus + n8n
```

### LiteLLM Model Tiers

| Tier | Model | Backend | Used For |
|------|-------|---------|----------|
| Tier 3 | `granite-nano` | Ollama (local) | Embeddings |
| Tier 2 | `mistral-nemo` | Ollama (local) | All 5 subagent scans |
| Tier 1 | `granite-heavy` | watsonx.ai | Final plan synthesis only |

IBM Cloud credit conservation: Tier 2/3 use local Ollama (free). Tier 1 (watsonx.ai) is called once per plan.

---

## Project Structure

```
onboarding-agent/
├── src/
│   ├── server.ts                    Express entrypoint, all 10 routes
│   ├── security/
│   │   ├── lobster-trap.ts          12-pattern prompt injection firewall
│   │   └── keycloak-auth.ts         JWT validation + DEV_BYPASS_AUTH
│   ├── ingestion/
│   │   ├── types.ts                 RawArtifact interface + makeArtifact()
│   │   ├── platform.ts              File-walk: platform/ → RawArtifact[]
│   │   ├── github.ts                Octokit: README, ADRs, closed issues
│   │   ├── curriculum.ts            Directus CMS: programme_guides
│   │   └── evalos.ts                EvalOS domains + C1000-207 fallback
│   ├── context-store/
│   │   ├── chroma-client.ts         ChromaDB client (onboarding-corpus)
│   │   ├── chunker.ts               Role-aware chunking
│   │   ├── index.ts                 Batch upsert pipeline
│   │   └── retriever.ts             HNSW cosine search + role filtering
│   ├── orchestrator/
│   │   ├── skills-assessor.ts       Role → 3 subagents, parallel RAG + scan
│   │   ├── verify.ts                File-system + RHOAI live-check
│   │   ├── planner.ts               granite-heavy synthesis, confidence gate
│   │   └── subagents/
│   │       ├── types.ts             OnboardingRole, SubagentFinding
│   │       ├── base-scan.ts         Abstract: LiteLLM + Zod + retry
│   │       ├── evalos-scan.ts       Bootcamp Student focus
│   │       ├── ailab-scan.ts        AI/ML Engineer (RHOAI stale-doc flag)
│   │       ├── infra-scan.ts        Platform Engineer
│   │       ├── backend-scan.ts      Backend Engineer
│   │       └── model-scan.ts        AI/ML model evaluation focus
│   └── render/
│       ├── markdownPlan.ts          Markdown render
│       ├── graph.ts                 Mermaid Gantt + service topology
│       └── taskSync.ts              2-stage CRM sync (one-click gate)
├── openshift/
│   ├── namespace.yaml               i3-onboarding namespace
│   ├── deploy.yaml                  Deployment, Service, Route, HPA
│   └── argocd-app.yaml              ArgoCD Application (wave 7)
├── scripts/
│   ├── mock-litellm.mjs             Local mock AI gateway (no cluster needed)
│   └── test-local.ps1               35-test automated suite (PowerShell)
├── Dockerfile                       Multi-stage UBI9 build
├── .env.example                     All env vars documented (no secrets)
├── package.json
└── tsconfig.json
```

### Platform Files Modified

| File | Change |
|------|--------|
| `platform/gitops/argocd/app-of-apps.yaml` | Wave 7 added to ApplicationSet + i3-onboarding destination |
| `platform/admissions/mcp/mcp_connectors.py` | `/tools/onboarding/sync-tasks` + `/confirm/{token}` endpoints |
| `platform/testing/testing.py` | Section 5: RAGAS onboarding evaluation (`--ragas-onboarding`) |
| `Makefile` | Section 11: `deploy-onboarding`, `build-onboarding`, `test-onboarding` |
| `.env.example` | 20 onboarding env vars added |

---

## Running Locally (No Docker, No Cluster, No Tokens)

### Prerequisites
- Node.js ≥ 20
- npm ≥ 9
- Python ≥ 3.10 (for ChromaDB)

### Step 1 — Install & configure

```powershell
cd onboarding-agent
npm install
copy .env.example .env
```

Edit `.env` and set:
```ini
DEV_BYPASS_AUTH=true
LITELLM_URL=http://localhost:4000/v1
LITELLM_KEY=local-test-key
CHROMA_HOST=localhost
CHROMA_PORT=8000
PLATFORM_REPO_PATH=../platform
```

### Step 2 — Open 4 terminals

**Terminal 1 — Mock AI Gateway**
```powershell
node scripts/mock-litellm.mjs
# → listening on http://localhost:4000
```

**Terminal 2 — Vector Database**
```powershell
npx --yes chromadb@latest
# → Application startup complete (port 8000)
```

**Terminal 3 — The Agent**
```powershell
npm run dev
# → i3 Onboarding Agent listening on :3000
```

**Terminal 4 — Index the codebase (once)**
```powershell
npm run ingest
# → chunks upserted into ChromaDB
```

### Step 3 — Generate a plan

```powershell
# Generate a Platform Engineer onboarding plan
$r = Invoke-RestMethod http://localhost:3000/api/onboarding/plan `
  -Method POST -ContentType "application/json" `
  -Body '{"role":"platform_engineer"}'

# View tasks
$r.plan.tasks | Format-Table day, verified, priority, title -Wrap

# View stale-doc detections (the key demo moment)
$r.plan.tasks | Where-Object { -not $_.verified } | Format-List title, verificationNote

# Get the Markdown plan
Invoke-RestMethod "http://localhost:3000/api/onboarding/plan/$($r.planId)/markdown"
```

### Step 4 — Run the automated test suite

```powershell
npm run test:local
# → 35/35 tests passed ✅
```

---

## API Reference

| Method | Endpoint | Gate | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | none | Liveness probe |
| `GET` | `/ready` | none | Readiness — checks ChromaDB |
| `POST` | `/api/onboarding/plan` | 🟢 auto | Generate plan. Body: `{"role":"..."}` |
| `GET` | `/api/onboarding/plan/:id` | 🟢 auto | Retrieve plan JSON |
| `GET` | `/api/onboarding/plan/:id/markdown` | 🟢 auto | Markdown render |
| `GET` | `/api/onboarding/plan/:id/gantt` | 🟢 auto | Mermaid Gantt chart |
| `GET` | `/api/onboarding/graph` | 🟢 auto | Service topology diagram |
| `POST` | `/api/onboarding/sync/prepare` | 🟡 one-click | Stage-1 CRM sync |
| `POST` | `/api/onboarding/sync/confirm/:id` | 🟡 one-click | Stage-2 CRM sync |
| `DELETE` | `/api/onboarding/sync/:id` | 🟢 auto | Cancel sync |
| `POST` | `/api/onboarding/ingest` | 🔴 admin | Re-index corpus |
| `GET` | `/api/onboarding/status` | 🟢 auto | System stats |

### Valid Roles

| Value | Target |
|-------|--------|
| `platform_engineer` | DevOps / SRE / Cloud engineers |
| `ai_ml_engineer` | LLM pipeline and agent engineers |
| `bootcamp_student` | AI bootcamp programme students |
| `backend_engineer` | Backend API and data model developers |
| `security_engineer` | Auth, secrets, and compliance engineers |

---

## RampUpPlan JSON Schema

```jsonc
{
  "schemaVersion": "1.0",
  "generatedAt": "2026-08-29T10:00:00.000Z",
  "role": "platform_engineer",
  "architecturalSummary": {
    "clusterVersion": "ROKS 4.15",
    "region": "eu-de (Frankfurt)",
    "namespaceCount": 12,
    "keyServices": [...],
    "forbiddenActions": ["Never modify solution-01..08 namespaces", ...],
    "creditBudget": "$14,047.27 IBM Cloud credits expiring October 2026"
  },
  "tasks": [
    {
      "day": 1,
      "title": "Install project-specific developer tools",
      "description": "Run `make help` to list all Makefile targets...",
      "filePaths": ["Makefile", "RUNBOOK.md"],
      "verified": true,
      "verificationNote": "all referenced paths confirmed present",
      "priority": "high",
      "estimatedHours": 2,
      "historicalIssueRef": "closed-issue #42: accidental solution-03 modification",
      "roles": ["platform_engineer"],
      "confidence": 0.97
    },
    {
      "day": 2,
      "title": "Needs verification: Explore RHOAI AI Lab Namespace (referenced path not found — likely stale doc)",
      "verified": false,
      "verificationNote": "RHOAI/i3-ai-lab namespace not live — platform-documentation.md states 'available from Month 3'",
      "confidence": 0.91
    }
  ],
  "totalVerified": 7,
  "totalUnverified": 2,
  "staleDocWarnings": ["docs/platform-documentation.md"]
}
```

---

## Security Design

### Lobster Trap — 12 Prompt Injection Patterns

Applied to every user-supplied text field **before** any LLM call:

| # | Pattern | Catches |
|---|---------|---------|
| 1 | `ignore\s+(all\s+)?previous\s+instructions?` | Classic injection |
| 2 | `you\s+are\s+now\s+(?!an?\s+(onboarding\|platform\|i3))` | Persona hijack |
| 3 | `act\s+as\s+(?!an?\s+(onboarding\|platform\|i3))` | Role override |
| 4 | `system\s*(prompt\|message\|instruction)` | System prompt exfil |
| 5 | `jailbreak` | Jailbreak attempts |
| 6 | `DAN\s+mode` | DAN variant |
| 7 | `<\s*(script\|img\|iframe\|svg)` | HTML/XSS |
| 8 | `(drop\|delete\|truncate)\s+table` | SQL DDL |
| 9 | `SELECT\s+.+FROM\s+` | SQL exfil |
| 10 | `prompt\s+injection` | Self-referential |
| 11 | `disregard\s+(all\s+)?previous` | Override variant |
| 12 | `\bexfiltrate\b` | Data exfil intent |

### Human Approval Gates

| Gate | Colour | Routes |
|------|--------|--------|
| Automatic | 🟢 | Plan generation, plan retrieval, render endpoints |
| One-click | 🟡 | CRM task sync (2-stage token confirmation, 5-min TTL) |
| Never auto | 🔴 | Writes to EvalOS tables, Keycloak realm/users |

### Secrets

All secrets injected at runtime from **OpenBao KV v2** at path `i3/onboarding-agent/`. No secrets in code or git. `LITELLM_KEY`, `CHROMA_TOKEN`, `DIRECTUS_TOKEN`, `EVALOS_API_KEY`, `GITHUB_TOKEN` are OpenBao-only.

---

## Deployment

```
git push → Tekton i3-build-deploy pipeline
  ├── npm ci + tsc
  ├── buildah bud -f Dockerfile (UBI9, non-root UID 1001)
  ├── trivy image scan
  └── oc rollout → i3-onboarding namespace

ArgoCD wave 7 → platform/gitops/argocd/app-of-apps.yaml
  Route: https://onboarding.i3technologies.co.ke
  HPA: 1–3 replicas (CPU 70%)
  Resources: 100m–500m CPU, 256Mi–512Mi memory
```

---

## Testing

```powershell
# Automated 35-test local suite
npm run test:local

# TypeScript typecheck (zero errors)
npm run typecheck

# Build
npm run build

# RAGAS quality evaluation (requires live agent + cluster)
python platform/testing/testing.py --ragas-onboarding
# Faithfulness ≥ 0.80, Answer Relevancy ≥ 0.75

# Red-team (50 tests, requires promptfoo)
make test-redteam
```

---

## Environment Variables

See [`.env.example`](onboarding-agent/.env.example) for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `DEV_BYPASS_AUTH` | Set `true` for local development — skips Keycloak JWT validation |
| `LITELLM_URL` | LiteLLM gateway URL (cluster-internal or `http://localhost:4000/v1`) |
| `CHROMA_HOST` / `CHROMA_PORT` | ChromaDB endpoint |
| `CHROMA_COLLECTION` | Collection name (default: `onboarding-corpus`) |
| `KEYCLOAK_ISSUER` | Keycloak realm URL |
| `PLATFORM_REPO_PATH` | Path to the platform/ repo for corpus ingest |

---

## Hard Constraints

> ⛔ **These rules are enforced in code and must never be bypassed:**
> - Never modify `solution-01` through `solution-08` namespaces
> - Never auto-write to EvalOS tables or Keycloak without 🔴 manual approval
> - Never hardcode secrets — OpenBao KV v2 only
> - Never skip the Lobster Trap firewall on user-supplied input
> - Never use `granite-heavy` (watsonx.ai) for anything except final plan synthesis

---

## Links

| Resource | URL |
|----------|-----|
| Live API | https://onboarding.i3technologies.co.ke |
| Keycloak SSO | https://sso.i3technologies.co.ke/realms/i3 |
| LiteLLM Gateway | https://litellm.i3technologies.co.ke/v1 |
| Platform Docs | `platform/docs/platform-documentation.md` |
| RUNBOOK | `platform/RUNBOOK.md` |
| ArgoCD | `platform/gitops/argocd/app-of-apps.yaml` |

---

## Built With

- [IBM ROKS 4.15](https://www.ibm.com/cloud/openshift) — Kubernetes cluster
- [IBM watsonx.ai](https://www.ibm.com/watsonx) — granite-heavy (Tier 1 synthesis)
- [LiteLLM](https://litellm.ai) — Sovereign LLM gateway
- [ChromaDB](https://www.trychroma.com) — Vector store
- [Keycloak](https://www.keycloak.org) — SSO authentication
- [OpenBao](https://openbao.org) — Secrets management
- [ArgoCD](https://argoproj.github.io/cd/) — GitOps deployment
- [Tekton](https://tekton.dev) — CI/CD pipeline
- [Express](https://expressjs.com) — HTTP framework
- [Zod](https://zod.dev) — Runtime schema validation

---

*IBM TechXchange Hackathon 2026 · i3 Agentic AI Labs · Project 1: Codebase Onboarding Agent*
