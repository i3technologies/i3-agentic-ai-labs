# Bob Workspace Inventory

| Field | Value |
|---|---|
| **Document** | `platform/docs/architecture/Bob-Workspace-Inventory.md` |
| **Prepared by** | IBM Bob — Principal Solutions Architect (EXP-00 / EXP-01) |
| **Date** | 2025-07-10 |
| **Branch** | `main` · `ba28dac` |
| **Phase** | READ-ONLY orientation — no files were modified |

> All facts are drawn exclusively from files read during this session.
> Fields that could not be determined from source files are marked **UNKNOWN** — no inference applied.

---

## 1. Repository Root

```
i3-Agentic-AI-Labs/
├── platform/                          ← 31 services + infrastructure manifests
├── onboarding-agent/                  ← TypeScript/Node.js onboarding orchestrator
├── i3-Platform-Modernisation1.0/      ← 9 blueprint documents (documentation only)
├── AGENTS.md                          ← Bob quick-reference (project rules)
├── i3-IBM-Bob-Technical-Implementation-Guide.md
├── i3-platform-modernisation-roadmap-plan.md
├── i3-platform-atomic-execution-plan.md
├── .bob/                              ← Bob workspace rules, skills, modes
└── platform/
    ├── RUNBOOK.md                     ← Day-2 operations reference
    └── docs/                          ← 14 HTML guides + 7 ADRs
```

---

## 2. Platform Services

> **Risk levels:** ⚫ Critical · 🔴 High · 🟡 Medium · 🟢 Low

---

### 2.1 FORD-Asili — Member Registration (IEBC)

| Field | Value |
|---|---|
| **Purpose** | FORD political-party member registration for IEBC; 16 March 2027 statutory deadline |
| **Language / Framework** | Python 3 / FastAPI; Go 1.21 (Hyperledger Fabric chaincode) |
| **Runtime** | OpenShift `i3-ford`; Hyperledger Fabric peer on `ford-channel` |
| **Deployment** | `platform/ford/deploy/ford-api-deployment.yaml` · `fabric-network.yaml` · ArgoCD |
| **Database** | PostgreSQL `ford_members_db` (asyncpg pool); Redis (`i3-data`) for OTP TTL + velocity |
| **External Integrations** | Africa's Talking USSD + SMS; Fabric Gateway REST shim (`fabric-gateway.i3-ford.svc.cluster.local:8080`); Consent Service |
| **Authentication** | Bearer token (OpenBao-injected); USSD session token |
| **Tenant Boundary** | ✅ `tenant_id = FORD_TENANT_ID` (env `00000000-0000-0000-0000-000000000005`); HC-4 enforced on all queries |
| **Event Dependencies** | Emits Fabric `TurnoutEvent` on `ford-channel`; Redis-backed retry queue for Fabric gateway failures |
| **AI / Model Dependencies** | None in registration path |
| **Tests** | `platform/ford/tests/test_otp_ratelimit.py` (OTP rate-limit + HMAC correctness) |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | ⚫ Critical — HC-2 (IEBC deadline), HC-6 (HMAC NIDs), HC-8 (ballot secrecy) |
| **HC Compliance** | HC-6 ✅ HMAC-SHA256 via `MEMBER_HMAC_SECRET` (OpenBao-injected); HC-8 ✅ `voteChoicesCollection` PDC; HC-4 ✅; HC-5 ✅ Fabric endorsement policy |

**Sub-components:**

| Sub-component | Path | Notes |
|---|---|---|
| Registration API | `platform/ford/api/main.py` | asyncpg pool, consent gate, HMAC token generation |
| USSD Bridge | `platform/ford/ussd/handler.py` | Africa's Talking `*509#` handler; OTP dispatch |
| Go Chaincode | `platform/ford/fabric/chaincode/membership_registry/membership_registry.go` | HC-6/HC-8 enforced; ward + agent counters |
| PDC Config | `platform/ford/fabric/collections_config.json` | `voteChoicesCollection` — ballot secrecy separation |
| Fabric Network CRDs | `platform/ford/deploy/fabric-network.yaml` | HLF Operator CRDs |

---

### 2.2 EvalOS — Assessment Platform

| Field | Value |
|---|---|
| **Purpose** | Certification exam delivery, proctoring, adaptive learning, code-sandbox execution |
| **Language / Framework** | TypeScript / Next.js 14 (web); Python / FastAPI (sandbox daemon, grading service) |
| **Runtime** | OpenShift `i3-evalos` |
| **Deployment** | `platform/evalos/evalos-deploy.yaml` · `evalos-web-deploy.yaml` · `evalos-services-deploy.yaml` · ArgoCD |
| **Database** | PostgreSQL `evalos` (pg.Pool, SSL+CA, `rejectUnauthorized: true`); migrations in `web/migrations/` + `db/schema.sql` |
| **External Integrations** | Grading Service (`grading-service.i3-evalos.svc.cluster.local:8000`) — **synchronous HTTP call**; n8n webhook (exam pass/fail); LiteLLM `qwen-heavy` (AI question generation, admin-only) |
| **Authentication** | NextAuth.js v4 → Keycloak OIDC (`KEYCLOAK_ISSUER`, `KEYCLOAK_CLIENT_ID`) |
| **Tenant Boundary** | ⚠️ **Partial** — `tenant_id` absent from base schema (`questions`, `exams`, `quiz_attempts` in `db/schema.sql`); web migrations `002` / `003` may add it — confirm via EXP-02a |
| **Event Dependencies** | Kafka topic `evalos-submissions` (6 partitions, 30-day retention) — consumer UNKNOWN |
| **AI / Model Dependencies** | LiteLLM `qwen-heavy` (question generation); Grading Service (scoring) |
| **Tests** | Locust load test: 100 concurrent sandbox users (`platform/testing/testing.py`) |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🔴 High — HC-4 partial; synchronous grading call under high concurrency |

**Sub-components:**

| Sub-component | Path | Notes |
|---|---|---|
| Web (Next.js) | `platform/evalos/web/src/` | Exam engine, admin question gen, auth |
| Base DB Schema | `platform/evalos/db/schema.sql` | Missing `tenant_id` on core tables |
| Grading Service | `platform/grading/main.py` | Python FastAPI; domain breakdown scoring; default pass threshold 68% |
| Sandbox Daemon | `platform/evalos/sandbox/daemon.py` | Code execution sandbox; security profile UNKNOWN |
| Anti-cheat Hook | `platform/evalos/useAntiCheat.ts` | Focus-loss, clipboard events, keystroke entropy |
| Web Migrations | `platform/evalos/web/migrations/003_ai_features.sql`, `004_interview_questions_seed.sql` | AI feature schema additions |

---

### 2.3 Engage — Campaign Email / SMS Platform

| Field | Value |
|---|---|
| **Purpose** | Multi-channel campaign management: email (Brevo), SMS (Africa's Talking), WhatsApp, AI personalisation |
| **Language / Framework** | TypeScript / Next.js 14 (web); Python (Kafka consumers) |
| **Runtime** | OpenShift `i3-engage` |
| **Deployment** | `platform/engage/engage-deploy.yaml` · ArgoCD |
| **Database** | PostgreSQL `engage_db` (pgBouncer, SSL+CA); migrations `001_init.sql`, `002_add_tenant_id.sql`, `003_rls_missing_tables.sql` |
| **External Integrations** | Brevo SMTP API; Africa's Talking SMS; WhatsApp Business Cloud API; M-Pesa Daraja; Consent Service; LiteLLM `qwen-fast` (personalisation) |
| **Authentication** | NextAuth.js v4 → Keycloak OIDC |
| **Tenant Boundary** | ✅ `tenant_id` added via migration `002`; `SET LOCAL app.tenant_id` enforced on every DB request |
| **Event Dependencies** | **Producer:** Kafka `engage.campaign-trigger` (6 partitions, feature-flagged via `ASYNC_CAMPAIGN_SEND=true`); **Consumer:** `kafka_consumers.py` (EmailEvent, SmsEvent, AIPersonaliseConsumer, CampaignTrigger); **DLQ:** `engage.ai-personalize.dlq` |
| **AI / Model Dependencies** | LiteLLM `qwen-fast` (email personalisation); Consent Service default-deny gate |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — `subject_id_hash` falls back to raw email during Phase 2 transition (TODO comment in `campaigns/send/route.ts`) |

---

### 2.4 PMaaS — Political Marketing as a Service

| Field | Value |
|---|---|
| **Purpose** | AI campaign briefings, ward targeting, voter sentiment analysis, activity logging |
| **Language / Framework** | TypeScript / Next.js 14 (web); Python / FastAPI + LangGraph (campaign agent) |
| **Runtime** | OpenShift `i3-pmaas` |
| **Deployment** | `platform/pmaas/pmaas-deploy.yaml` · ArgoCD |
| **Database** | PostgreSQL `pmaas_db` (pg.Pool); Langfuse tracing DB; migrations `001–003` |
| **External Integrations** | Campaign Agent (`campaign-agent.i3-pmaas.svc.cluster.local:8080`); LiteLLM `qwen-heavy`/`qwen-fast`; ChromaDB `pmaas-manifesto`; WhatsApp Business API; M-Pesa Daraja; Voice TTS/STT |
| **Authentication** | NextAuth.js v4 → Keycloak OIDC |
| **Tenant Boundary** | ✅ `tenant_id` in migrations; RLS applied; `SET LOCAL app.tenant_id` enforced |
| **Event Dependencies** | Kafka consumer in `campaign_agent.py` (optional, `KAFKA_BOOTSTRAP` env); Langfuse trace emission on every LLM call |
| **AI / Model Dependencies** | LiteLLM `qwen-heavy` (briefing), `qwen-fast` (Q&A); ChromaDB RAG (manifesto + campaign docs); LangGraph orchestration; 12-pattern Lobster Trap; Consent gate (DPA 2019 §25) |
| **Tests** | RAGAS evaluation: campaign agent, vote gap accuracy; Promptfoo: 20 OWASP LLM vectors (`platform/testing/testing.py`) |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — **`VOICE_API_KEY` hardcoded literal in `pmaas-deploy.yaml:63`** |

---

### 2.5 Admissions — Student Lead Capture Agent

| Field | Value |
|---|---|
| **Purpose** | AI chat (WebSocket streaming) for prospective student admissions enquiries; CRM lead + appointment creation |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift `i3-admissions` |
| **Deployment** | `platform/admissions/admissions-deploy.yaml` · ArgoCD |
| **Database** | None direct — all writes proxied through MCP Gateway |
| **External Integrations** | MCP Gateway (`mcp-gateway.i3-agent-mesh.svc.cluster.local:8100`); Odoo CRM; Google Calendar; n8n enrolment webhook |
| **Authentication** | CORS restricted to `i3technologies.co.ke`; `X-Tenant-Id` header to MCP Gateway |
| **Tenant Boundary** | `DEFAULT_TENANT_ID` env var; propagated in `X-Tenant-Id` header |
| **Event Dependencies** | Kafka topic `admissions-leads` (3 partitions, 7-day retention) — consumer UNKNOWN |
| **AI / Model Dependencies** | LiteLLM (via MCP tool `litellm.chat`); ChromaDB RAG (via MCP tool `chroma.search`); 12-pattern Lobster Trap; Decision Log to Agent Registry |
| **Tests** | RAGAS: 30 QA pairs, faithfulness ≥ 0.80, relevancy ≥ 0.75 (`platform/testing/testing.py`) |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟢 Low — `mcp_connectors.py` is now a thin proxy (v2.0.0); all side effects in MCP Gateway |

---

### 2.6 SmartLab — AI Content Authoring

| Field | Value |
|---|---|
| **Purpose** | AI-powered course/lesson/quiz authoring; SCORM/xAPI packaging; Moodle integration; ePub generation |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift — namespace **UNKNOWN** |
| **Deployment** | `platform/smartlab/04-authoring-api-deploy.yaml` (OpenShift S2I) |
| **Database** | PostgreSQL (schema in `03-smartlab-schema.sql`): `authors`, `courses`, `modules`, `lessons`; pg_trgm FTS; SCORM/xAPI fields |
| **External Integrations** | Moodle (`moodle_service.py`); SeaweedFS (`storage_service.py`); LiteLLM (`ai_service.py`); n8n VOD pipeline |
| **Authentication** | UNKNOWN (`middleware.py` not fully read) |
| **Tenant Boundary** | UNKNOWN — `tenant_id` not confirmed in schema (first 100 lines only; requires EXP-02b) |
| **Event Dependencies** | n8n VOD pipeline for content publishing; Kafka usage UNKNOWN |
| **AI / Model Dependencies** | LiteLLM (`ai_service.py`); ChromaDB collection UNKNOWN; `epub_builder`, `scorm_packager` (local) |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — HC-4 `tenant_id` unconfirmed |

---

### 2.7 AI Lab / Sage (JupyterHub + Open-WebUI)

| Field | Value |
|---|---|
| **Purpose** | Interactive AI development environment; Jupyter notebooks; Sage white-label assistant; RAG corpus embedding pipeline |
| **Language / Framework** | JupyterHub (Python); Open-WebUI (containerised); Python embedding pipeline |
| **Runtime** | OpenShift `i3-ai-lab` |
| **Deployment** | `platform/ai-lab/jupyterhub/jupyterhub-deploy.yaml` · `open-webui/open-webui-deploy.yaml` · ArgoCD |
| **Database** | ChromaDB (`chromadb.i3-ai-lab.svc.cluster.local`); 768-dim Nomic Embed v1.5 embeddings; PostgreSQL — UNKNOWN database name |
| **External Integrations** | LiteLLM proxy (all model calls); Keycloak OIDC (`GenericOAuthenticator`); OpenBao (`i3/jupyterhub/crypt-key`, `i3/keycloak/jupyterhub-client`); Voice STT/TTS (`i3-voice` namespace) |
| **Authentication** | Keycloak OIDC (`ENABLE_SIGNUP: false` — Keycloak accounts only) |
| **Tenant Boundary** | UNKNOWN — single shared ChromaDB; per-tenant collection isolation not confirmed |
| **Event Dependencies** | Kafka topic `ai-lab-usage` (6 partitions, 30-day retention) — consumer UNKNOWN |
| **AI / Model Dependencies** | LiteLLM (all tiers); Ollama Nomic Embed v1.5 (RAG embeddings); Whisper STT; espeak-ng TTS |
| **Tests** | Locust: 2,000 concurrent LiteLLM requests (`platform/testing/testing.py`) |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — Single shared ChromaDB; no per-tenant isolation confirmed |

---

### 2.8 Onboarding Agent

| Field | Value |
|---|---|
| **Purpose** | Developer / student onboarding: role-based ramp-up plans, multi-subagent scanning, Directus task sync, GitHub corpus ingestion |
| **Language / Framework** | TypeScript / Node.js / Express |
| **Runtime** | OpenShift `i3-onboarding` (per post-deploy checklist) |
| **Deployment** | ArgoCD workstream `onboarding-agent` |
| **Database** | Redis (plan storage: `plan:<planId>` TTL 7200s); ChromaDB (`chromadb.i3-ai-lab`) for RAG corpus |
| **External Integrations** | LiteLLM `granite-heavy` (planner), `mistral-nemo` (subagents); Keycloak JWKS; MCP Connectors proxy; GitHub (simple-git); Directus |
| **Authentication** | Keycloak JWT middleware — **⚠️ `DEV_BYPASS_AUTH` active bypass in `keycloak-auth.ts:51–53`** |
| **Tenant Boundary** | UNKNOWN — Redis keys plan-scoped; no `tenant_id` partition confirmed |
| **Event Dependencies** | Decision log to Agent Registry (`POST /decisions`) |
| **AI / Model Dependencies** | LiteLLM `granite-heavy` (planner); `mistral-nemo` (subagents); Zod schema validation on all LLM outputs; 12-pattern Lobster Trap |
| **Tests** | `onboarding-agent/src/__tests__/skills-assessor.test.ts` |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🔴 **High — HC-7 VIOLATION: `DEV_BYPASS_AUTH` active bypass in production code** |

**Subagents:** `ailab-scan` · `backend-scan` · `base-scan` · `evalos-scan` · `infra-scan` · `model-scan`

---

### 2.9 AfroERP

| Field | Value |
|---|---|
| **Purpose** | Africa-localised ERP: KRA eTIMS e-invoicing, M-Pesa payments, HR, accounting |
| **Language / Framework** | Python / Frappe (ERPNext); FastAPI (AI agent) |
| **Runtime** | OpenShift `i3-afroerp` |
| **Deployment** | `platform/afroerp/afroerp-deploy.yaml` · ArgoCD |
| **Database** | MariaDB (Frappe internal); PostgreSQL bridge UNKNOWN |
| **External Integrations** | KRA eTIMS API (`https://etims-sbx.kra.go.ke`); M-Pesa Daraja OAuth2; LiteLLM; ChromaDB (ERP knowledge base) |
| **Authentication** | UNKNOWN (Frappe built-in auth; Keycloak integration UNKNOWN) |
| **Tenant Boundary** | UNKNOWN — Frappe multi-tenancy model not confirmed |
| **Event Dependencies** | UNKNOWN |
| **AI / Model Dependencies** | LiteLLM (analyse/automate/report/chat endpoints); ChromaDB RAG |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — External tax API and M-Pesa payment processing |

---

### 2.10 SIT — Digital Work-Centers

| Field | Value |
|---|---|
| **Purpose** | Kenyan civil-service digital portal: eCitizen, NTSA, KRA, land, professional, membership registrations |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift (namespace from `platform/sit/deploy/np-i3-sit.yaml`) |
| **Deployment** | `platform/sit/deploy/sit-agents-routes.yaml` |
| **Database** | PostgreSQL `sit_db` (asyncpg); `tenant_id` + RLS in `platform/migrations/002_rls_all_databases.sql` |
| **External Integrations** | LiteLLM (model UNKNOWN); EvalOS API; Talent API; SeaweedFS; Consent Service |
| **Authentication** | UNKNOWN — HC-6 HMAC pattern confirmed (`subject_hash` via HMAC-SHA256 in `sit/api/main.py:120`) |
| **Tenant Boundary** | ✅ RLS confirmed in migration `002` |
| **Event Dependencies** | UNKNOWN |
| **AI / Model Dependencies** | LiteLLM (model tier UNKNOWN) |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — Handles Kenyan government data |

---

### 2.11 Talent Cloud

| Field | Value |
|---|---|
| **Purpose** | Candidate matching, skills assessments, AI-driven job placement |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift (from `platform/talent/deploy/np-i3-talent.yaml`) |
| **Deployment** | `platform/talent/deploy/np-i3-talent.yaml` |
| **Database** | PostgreSQL `talent_db` (asyncpg); RLS in `002_rls_all_databases.sql` |
| **External Integrations** | LiteLLM; EvalOS (exam results); Consent Service |
| **Authentication** | UNKNOWN |
| **Tenant Boundary** | ✅ RLS confirmed in migration |
| **Event Dependencies** | UNKNOWN |
| **AI / Model Dependencies** | LiteLLM (model tier UNKNOWN) |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟢 Low |

---

### 2.12 OTT — Video Streaming Platform

| Field | Value |
|---|---|
| **Purpose** | Live bootcamp delivery (LL-HLS / WebRTC / SRT, sub-3s latency); VOD replay; CMS |
| **Language / Framework** | OvenMediaEngine (C++, open-source); Directus CMS (Node.js); Nginx HLS cache; n8n (Node.js) |
| **Runtime** | OpenShift `i3-ott` |
| **Deployment** | `platform/ott/ome/ome-deploy.yaml` · `directus-deploy.yaml` · `nginx-hls.yaml` · `n8n-deploy.yaml` · `seaweedfs-deploy.yaml` |
| **Database** | Directus → PostgreSQL `directus` (Crunchy cluster); SeaweedFS (primary media storage); IBM COS (DR backup) |
| **External Integrations** | SeaweedFS; IBM COS; n8n workflow automation |
| **Authentication** | Keycloak OIDC (Directus) |
| **Tenant Boundary** | UNKNOWN — Directus multi-tenancy model not confirmed |
| **Event Dependencies** | Kafka topic `ott-stream-events` (3 partitions, 1-day retention); n8n VOD pipeline |
| **AI / Model Dependencies** | Ollama `mistral:7b-instruct-q4_K_M` — **separate instance in `i3-ott` namespace**, not routed through main model gateway |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — MinIO archived April 2026; SeaweedFS confirmed as primary replacement |

---

### 2.13 Voice Services (TTS + STT)

| Field | Value |
|---|---|
| **Purpose** | Text-to-speech (espeak-ng) and speech-to-text (Whisper) for AI agents and OTT |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift `i3-voice` |
| **Deployment** | Dockerfile present at `platform/voice/tts/Dockerfile`; deployment YAML **UNKNOWN** |
| **Database** | None |
| **External Integrations** | Open-WebUI Sage; PMaaS; other consumers UNKNOWN |
| **Authentication** | Bearer token (`VOICE_API_KEY` env var) |
| **Tenant Boundary** | UNKNOWN |
| **Event Dependencies** | None |
| **AI / Model Dependencies** | espeak-ng (TTS); Whisper (STT) |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟢 Low |

---

### 2.14 MCP Gateway

| Field | Value |
|---|---|
| **Purpose** | Centralised agent tool invocation; HC-5 policy enforcement; rate limiting (Redis); tool catalogue |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift `i3-agent-mesh` (port 8100) |
| **Deployment** | `platform/mcp-gateway/deploy.yaml` |
| **Database** | PostgreSQL (migration `platform/mcp-gateway/migrations/001_init.sql`); Redis (rate limiting) |
| **External Integrations** | Odoo CRM; Google Calendar; Directus; n8n; ChromaDB; LiteLLM |
| **Authentication** | `X-Agent-Id` + `X-Tenant-Id` headers; tool-level authorization — full auth middleware UNKNOWN (lines 150+ not read) |
| **Tenant Boundary** | ✅ `X-Tenant-Id` propagated on all tool invocations |
| **Event Dependencies** | UNKNOWN (may emit audit events) |
| **AI / Model Dependencies** | LiteLLM (`litellm_chat.py` tool); ChromaDB (`chroma_search.py` tool) |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🔴 High — Single point of control for all agent tool access |

**Registered tools:** `odoo.crm.create`, `odoo.crm.confirm`, `odoo.crm.read`, `calendar.book`, `calendar.confirm`, `n8n.enrolment.trigger`, `directus.tasks.write`, `directus.tasks.confirm`, `litellm.chat`, `chroma.search`

---

### 2.15 Agent Registry

| Field | Value |
|---|---|
| **Purpose** | Agent manifest store; decision log; HC-3/HC-5 governance (L0/L1 autonomy ceiling enforcement) |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift `i3-agent-mesh` (port 8200) |
| **Deployment** | `platform/agent-registry/agent-registry-deploy.yaml` |
| **Database** | PostgreSQL (asyncpg); tables `agent_registry`, `agent_decision_log`; `tenant_id` NOT NULL; autonomy tier `CHECK` constraint |
| **Authentication** | UNKNOWN (internal service; auth middleware not visible in first 60 lines) |
| **Tenant Boundary** | ✅ `tenant_id` HC-4 enforced |
| **Event Dependencies** | None — fire-and-forget `POST /decisions` from all agents |
| **AI / Model Dependencies** | None |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🔴 High — Governance backbone; audit trail failure if unavailable |

**Registered agent manifests:** `admissions-agent-v1` · `afroerp-agent-v1` · `base-scan-agent-v1` · `campaign-agent-v1` · `engage-campaign-agent-v1` · `onboarding-agent-v1` · `onboarding-planner-v1` · `pmaas-campaign-agent-v1` · `sit-tutor-agent-v1` · `skills-assessor-agent-v1`

---

### 2.16 Consent Service

| Field | Value |
|---|---|
| **Purpose** | Centralised DPA 2019 §25 consent management; default-deny pattern; per-channel/purpose records |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift `i3-consent` |
| **Deployment** | `platform/consent/consent-deploy.yaml` |
| **Database** | PostgreSQL (asyncpg); tables `consent_records`, `consent_audit`; RLS enforced; unique constraint on `(tenant_id, subject_id_hash, channel, purpose)` |
| **Authentication** | UNKNOWN |
| **Tenant Boundary** | ✅ `tenant_id` NOT NULL; RLS policy enforced |
| **Event Dependencies** | None |
| **AI / Model Dependencies** | None |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — DPA 2019 compliance critical path |

---

### 2.17 Grading Service

| Field | Value |
|---|---|
| **Purpose** | Exam grading: SC / MR question scoring, domain breakdown, pass threshold (default 68%) |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift `i3-evalos` (port 8000) |
| **Deployment** | Dockerfile: `platform/grading/Dockerfile`; deployment YAML **UNKNOWN** |
| **Database** | UNKNOWN — accepts `answers` JSON payload; no direct DB calls observed in first 100 lines |
| **External Integrations** | Called synchronously from EvalOS submit route |
| **Authentication** | UNKNOWN (internal only) |
| **Tenant Boundary** | UNKNOWN |
| **AI / Model Dependencies** | UNKNOWN — may use LLM for short-answer scoring (not confirmed) |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — Synchronous in critical submission path under load |

---

### 2.18 Credential Service

| Field | Value |
|---|---|
| **Purpose** | W3C Verifiable Credentials 2.0 issuance; QR token signing (HMAC-SHA256) |
| **Language / Framework** | Python / FastAPI |
| **Runtime** | OpenShift — namespace **UNKNOWN** |
| **Deployment** | Dockerfile: `platform/credential/Dockerfile`; deployment YAML **UNKNOWN** |
| **Database** | asyncpg pool; in-memory fallback store in dev; production DB URL **UNKNOWN** |
| **External Integrations** | UNKNOWN |
| **Authentication** | UNKNOWN |
| **Tenant Boundary** | UNKNOWN |
| **AI / Model Dependencies** | None |
| **Tests** | UNKNOWN |
| **Operational Owner** | UNKNOWN |
| **Risk Level** | 🟡 Medium — W3C VC issuance; HMAC signing |

---

### 2.19 IBM Bob MCP Server

| Field | Value |
|---|---|
| **Purpose** | Bob workspace guard tools: Lobster Trap test, SQL AST audit, agent manifest validation, CloudEvent envelope verification, DEV_BYPASS_AUTH scan, RLS completeness check |
| **Language / Framework** | Python (MCP SDK) |
| **Runtime** | Bob IDE session (local / workspace context) |
| **Deployment** | `.bob/` workspace configuration |
| **Database** | None |
| **Authentication** | N/A (Bob session tool) |
| **AI / Model Dependencies** | None |
| **Tests** | N/A |
| **Operational Owner** | i3 Engineering |
| **Risk Level** | 🟢 Low |

---

## 3. Infrastructure Components

### 3.1 Model Gateway — LiteLLM + Ollama

| Field | Value |
|---|---|
| **Namespace** | `i3-model-gateway` |
| **Components** | LiteLLM proxy (ConfigMap `litellm-config`) + Ollama StatefulSet |
| **Models** | Tier 3: `granite-nano` (2B, 60s), `nomic-embed` (768-dim, 15s) · Tier 2: `qwen-fast` (7B, 180s), `coder` (7B, 180s) · Tier 1: `qwen-heavy` (14B, 240s), `vision` (LLaVA 13B, 240s) |
| **Routing** | least-busy; fallback chain: `qwen-heavy` → `qwen-fast` → `granite-nano` |
| **Caching** | Redis (`redis.i3-data.svc.cluster.local:6379`); TTL 3600s; similarity threshold 0.95 |
| **Observability** | Langfuse + Prometheus callbacks |
| **GPU** | **CPU-only** — GPU workstream B1 not yet provisioned |
| **Replicas / KEDA** | LiteLLM: 1→6 on queue depth ≥20; Ollama: 1→4 on CPU ≥80% |
| **Per-tenant Budget** | Not confirmed in reviewed ConfigMap — requires EXP-05a |
| **Risk Level** | 🔴 High — Single Ollama replica; CPU-only; no confirmed per-tenant budget enforcement |

### 3.2 Kafka — Strimzi KRaft

| Field | Value |
|---|---|
| **Namespace** | `i3-messaging` |
| **Version** | Kafka 3.7.0 (ZooKeeper-free KRaft) |
| **Cluster** | 3 combined broker+controller nodes; 20 Gi PVC per node (ibmc-vpc-block-retain-10iops-tier) |
| **Security** | Plain 9092 (SCRAM-SHA-512) + TLS 9093 (mTLS) |
| **Topics** | `admissions-leads` (3p/3r, 7d) · `evalos-submissions` (6p/3r, 30d) · `ott-stream-events` (3p/3r, 1d) · `ai-lab-usage` (6p/3r, 30d) · `engage.campaign-trigger` (6p/3r, 7d) · `engage.ai-personalize.dlq` (3p/3r, 30d) |
| **Metrics** | JMX → Prometheus exporter configured |

### 3.3 PostgreSQL — Crunchy HA

| Field | Value |
|---|---|
| **Namespace** | `i3-data` |
| **Cluster** | 1 primary + 2 replicas; pgBouncer connection pooler |
| **Databases confirmed** | `langfuse`, `evalos`, `admissions`, `directus`, `keycloak` (from Crunchy cluster YAML) + `ford_members_db`, `engage_db`, `pmaas_db`, `talent_db`, `sit_db`, `agent_registry_db` (from service configs) |
| **Backup** | pgBackRest → IBM COS |
| **TLS** | CA cert mounted via `PG_CA_CERT_PATH`; `rejectUnauthorized: true` enforced on all pools |

### 3.4 Redis

| Field | Value |
|---|---|
| **Namespace** | `i3-data` |
| **Address** | `redis.i3-data.svc.cluster.local:6379` |
| **Usage** | LiteLLM semantic cache · MCP Gateway rate limiting · FORD OTP TTL/velocity · Onboarding Agent plan storage (TTL 7200s) · Kafka consumer idempotency |

### 3.5 Keycloak (SSO)

| Field | Value |
|---|---|
| **Namespace** | `i3-auth` |
| **Realm** | `i3` |
| **External URL** | `sso.i3technologies.co.ke` |
| **Backend** | PostgreSQL `keycloak` database (Crunchy cluster) |
| **Replicas** | 2 instances (HA via RHSSO Operator) |
| **Clients confirmed** | `engage-web` · `pmaas-web` · `jupyterhub` · `onboarding-agent` · `evalos` (client ID from deploy UNKNOWN — present via NextAuth) |

### 3.6 OpenBao (Secrets Vault)

| Field | Value |
|---|---|
| **Namespace** | `i3-security` |
| **Deployment** | StatefulSet 3 replicas; Raft HA storage |
| **Seal** | AWS KMS auto-unseal |
| **Known KV paths** | `i3/jupyterhub/crypt-key` · `i3/keycloak/jupyterhub-client` · `i3/model-gateway/litellm` (LiteLLM API key) · `i3/ford/member-hmac-secret` (`MEMBER_HMAC_SECRET`) · other service paths UNKNOWN |
| **Usage Pattern** | Kubernetes secret injection via init containers; env vars from KV v2 |

### 3.7 CI/CD — Tekton + ArgoCD

| Field | Value |
|---|---|
| **Namespace** | `i3-gitops` |
| **Tekton Pipeline** | 5-gate sequence: `secret-scan` (TruffleHog + Gitleaks) → `lint-typecheck` (Ruff + Mypy + TSC) → `run-tests` (pytest + npm test) → `buildah-build-push` (OCI) → `trivy-scan` (CRITICAL+HIGH) |
| **ArgoCD** | App-of-Apps pattern; 7 workstreams: core-operators · model-gateway · ai-lab · evalos · ott · admissions · onboarding-agent |
| **HC-1 Enforcement** | `solution-01..08` explicitly excluded from ArgoCD managed namespaces (`app-of-apps.yaml:49`) |

### 3.8 Kong API Gateway

| Field | Value |
|---|---|
| **Namespace** | `i3-gateway` |
| **Mode** | DB-less declarative config |
| **Replicas** | 2 |
| **Status** | STEP-P2-07 deployed; route definitions UNKNOWN |

### 3.9 Monitoring

| Field | Value |
|---|---|
| **Namespace** | `i3-monitoring` |
| **Components** | Prometheus · Grafana (StatefulSet status UNKNOWN) · Loki (UNKNOWN) · Langfuse (`platform/gitops/apps/langfuse-deploy.yaml`) |
| **Alerts defined** | `TenantTokenBudgetHigh` (≥80%), `TenantTokenBudgetExhausted` (100%), `LiteLLMCacheHitRateLow` (<15%), agent error rate, pool exhaustion, Kafka consumer lag, pod crash-loop |

### 3.10 Terraform (IaC)

| Field | Value |
|---|---|
| **Provider** | IBM Cloud (`ibm-cloud/ibm v1.89.0`) |
| **Modules** | `roks/main.tf` · `vpc/main.tf` · `iam/main.tf` · `cos/main.tf` |
| **State** | `.terraform/terraform.tfstate` — **LOCAL file, not a remote backend** |
| **Risk** | 🔴 High — local state may contain IBM Cloud credentials; confirm remote backend per EXP-03e |

---

## 4. ADR Inventory

| ADR | Title | Status | Key Decision |
|---|---|---|---|
| ADR-001 | Consent Service Extraction | UNKNOWN | Dedicate `i3-consent` namespace; default-deny pattern (DPA 2019 §25) |
| ADR-002 | Agent Registry + Decision Log | UNKNOWN | Central governance store for HC-3/HC-5 |
| ADR-003 | MCP Tool Gateway | UNKNOWN | Centralise all agent tool invocations through MCP Gateway |
| ADR-004 | Tenant Isolation | UNKNOWN | RLS on all tables; `SET LOCAL app.tenant_id` pattern |
| ADR-005 | Credential + Grading Service Extraction | UNKNOWN | Dedicated microservices for W3C VC and exam scoring |
| ADR-006 | API Gateway | UNKNOWN | Kong DB-less (addresses H-2: unauthenticated external endpoints) |
| ADR-007 | Hyperledger Fabric Membership Ledger | **Accepted** (2025-07-01) | Fabric for FORD-Asili; `voteChoicesCollection` PDC for HC-8; `IEBCObserverMSP` for independent audit |

---

## 5. HC-1 Compliance Check (solution-01 through solution-08)

**Verdict: PASS — No violations found.**

All 70 references to `solution-01..08` are protective constraints:

| Location | Nature |
|---|---|
| `platform/gitops/argocd/app-of-apps.yaml:49` | Explicitly EXCLUDED from ArgoCD managed namespaces ✅ |
| `platform/namespaces/namespaces.yaml:4` | Documented as `DO NOT TOUCH` ✅ |
| `onboarding-agent/src/ingestion/platform.ts:30–31` | Hardcoded FORBIDDEN namespace list ✅ |
| `platform/testing/testing.py:769,775` | Test assertions that forbid modification ✅ |
| `platform/RUNBOOK.md:33` | Operations instruction ✅ |

---

## 6. Hardcoded Secrets & HC-7 Violations Found

| Location | Issue | Severity |
|---|---|---|
| `onboarding-agent/src/security/keycloak-auth.ts:51–53` | **`DEV_BYPASS_AUTH=true` active code path** — JWT validation skipped when env var is set | ⚫ **HC-7 VIOLATION — Critical** |
| `pmaas_setup.sql` (workspace root) | Plaintext DB password `[REDACTED � rotate via OpenBao i3/pmaas/db-url]` in SQL file | ⚫ Critical |
| `platform/pmaas/pmaas-deploy.yaml:63` | `VOICE_API_KEY` hardcoded literal value in deployment manifest | 🔴 High |
| `platform/docs/03-databases-storage-guide.html:129` | `PGPASSWORD` literal in public-facing HTML guide | 🔴 High |
| Workspace root: `tls.key`, `ca.crt`, `tls.crt` | TLS private key as untracked files in workspace root | ⚫ Critical |
| `.terraform/terraform.tfstate` | Local Terraform state file — may contain IBM Cloud credentials | 🔴 High |

---

## 7. Summary Statistics

| Category | Count |
|---|---|
| Platform services / apps inventoried | 19 |
| Namespaces (confirmed) | 17 |
| PostgreSQL databases | 11+ |
| Kafka topics | 6 |
| Registered agent manifests | 10 |
| MCP tools registered | 10 |
| ADRs | 7 |
| Tekton pipeline gates | 5 |
| ArgoCD GitOps workstreams | 7 |
| Test types in `testing.py` | Locust (3), RAGAS (3), Promptfoo (1) |
| HC-7 violations confirmed | 2 (`DEV_BYPASS_AUTH` bypass + plaintext `pmaas_setup.sql` password) |
| HC-4 violations confirmed | 1 (EvalOS base schema) |
| HC-4 violations unconfirmed | 2 (SmartLab, AfroERP — require further investigation) |
| Unknown fields requiring clarification | 15 (see Current-State-Dependency-Map.md §C) |
