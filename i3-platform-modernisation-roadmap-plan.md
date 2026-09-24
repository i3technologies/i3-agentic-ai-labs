# i3 AI Platform — Incremental Modernisation Roadmap
## Architecture Plan Document

**Version:** 1.0  
**Classification:** Internal Engineering — Architecture  
**Status:** Pending User Approval  
**Source Reviews:**
- `i3-Enhancement 3/i3_Agentic_AI_Platform_Senior_Technical_Implementation_Guide.md`
- `i3-Enhancement 3/i3_PMC_Master_Technical_Implementation_Guide.md`
- `i3-Enhancement 3/i3 E³ Technical Implementation Guide.md`
- `i3-Enhancement 3/PMaaS_Consolidated_Technical_Implementation_Guide.md`
- `i3-Enhancement 3/Sovereign_Agentic_Collaboration_Platform_Full_Application_Blueprint.md`
- Full codebase audit of `platform/` and `onboarding-agent/`

---

## Overview

The i3 AI Platform is an event-driven, multi-tenant workload deployed on IBM ROKS 4.15 (Frankfurt)
across 11 managed namespaces, 7 ArgoCD GitOps waves, and 9 language-diverse service runtimes.
The existing infrastructure foundation — Kafka event backbone, LiteLLM model gateway, Keycloak OIDC,
Crunchy PostgreSQL HA, Strimzi Kafka KRaft, KEDA autoscaling, Tekton CI/CD — is production-grade
and should not be replaced.

The modernisation target, as defined across all Enhancement 3 guides, is a
**cloud-native, Domain-Driven, agentic platform** with:
1. Clean domain service boundaries (one bounded context per deployment unit)
2. An Agent Mesh with governed autonomy tiers, MCP Tool Gateway, and decision log
3. A unified observability plane (OTel traces from HTTP request through every LLM call)
4. Security hardening that closes the Critical and High findings from the static audit
5. A test harness that gates every merge to main automatically

This plan is divided into **three strictly-sequenced phases**. Phase 2 cannot begin
until Phase 1 exit criteria are met. Phase 3 cannot begin until Phase 2 exit criteria are met.
This is non-negotiable: domain decoupling on an unstable foundation creates worse coupling.

**Target Architecture Reference (Enhancement 3 — 8-Layer Model):**
- L1 Experience: Next.js 15, PWA, React 19
- L2 Edge & Gateway: OpenShift Routes, Kong/IBM API Connect, GraphQL BFF
- L3 Identity & Access: Keycloak, SPIFFE/SPIRE, OPA
- L4 Domain Services: FastAPI (AI-adjacent), Quarkus/Spring Boot (transactional)
- L5 Agentic Runtime: LangGraph, MCP servers, watsonx Orchestrate control plane
- L6 Knowledge & Data: PostgreSQL 16, Apache AGE graph, Milvus vector, OpenSearch, Kafka, Iceberg
- L7 Trust & Evidence: Hyperledger Fabric, W3C VC 2.0, HSM-backed keys
- L8 Platform & Operations: ROKS, ArgoCD, Tekton, OpenBao, OTel, Prometheus, Grafana, Loki

**Binding Architecture Principles (from i3 E³ guide — all 12 are enforced, not optional):**
- P1: Work Graph is the centre
- P2: Events are the spine (no synchronous cross-service chaining)
- P3: Agents propose, policy disposes
- P4: Open protocols at every seam (MCP, A2A, OTel, W3C VC, CloudEvents)
- P5: Portability over proximity (OCI containers, no managed-service lock-in on critical path)
- P6: Evidence by construction
- P7: Multi-tenant from line one (tenant_id on every row, event, log line)
- P8: Deterministic core, probabilistic edge
- P9: Small surface, deep contracts
- P10: Observable by default
- P11: Progressive autonomy
- P12: Privacy is a design input

---

## Phase 1: Foundation
### Core Refactor · Configuration Externalization · Test Harness

**Goal:** Make the existing platform safe, observable, and testable before any domain boundary
changes are made. Every Critical and High finding from the static audit must be resolved.
Every service must have a green test gate before Phase 2 begins.

---

### Phase 1 — Entry Criteria

- [ ] Codebase static audit complete (DONE — findings documented in audit report)
- [ ] Enhancement 3 guides reviewed and target architecture understood
- [ ] IBM Cloud credit balance and Red Hat OpenShift Partner Subscription confirmed
      (referenced as Risk #1 in i3 PMC guide — must be verified before engineering begins)
- [ ] OpenBao (Vault) is reachable and the KV v2 engine at `i3/` is unsealed

---

### Phase 1 — Sub-Tasks

#### P1-T1: Credential Rotation and Secret Hygiene
**Intent:** Close all Critical-severity credential exposure findings before any other work.
**Expected Outcomes:**
- No plaintext credentials exist in any file tracked by git
- All shell scripts that contained passwords are purged from git history or credentials rotated
- `.env.local` is removed from tracking and added to `.gitignore`
- CI/CD pipeline runs `trufflehog` or `gitleaks` as a blocking pre-commit hook
**Todo:**
- [ ] Rotate MariaDB root password (`REDACTED-mariadb-root`) found in `platform/scripts/setpw-root-pct.sh`
- [ ] Rotate ERPNext admin password (`REDACTED-erp-admin`) found in `platform/scripts/setup-erpnext-site.sh`
- [ ] Rotate Keycloak admin password (`REDACTED-keycloak-admin`) found in `platform/scripts/test_keycloak.sh`
- [ ] Rotate LiteLLM API key (`sk-litellm-i3-f951c9377163a11275864cb92e90ad13`) found in `platform/scripts/test_litellm_full.sh`
- [ ] Revoke and regenerate the PostgreSQL connection URL in `pmaas-secret-patch.json` (decoded: `postgresql://pmaas:REDACTED-pmaas-db@...`)
- [ ] Remove or rewrite all `platform/scripts/*.sh` files that embed passwords; store rotated credentials in OpenBao only
- [ ] Add `onboarding-agent/.env.local` to `.gitignore` and remove from git tracking
- [ ] Add `gitleaks` or `trufflehog` as a Tekton pipeline gate (blocking step before build)
- [ ] Add a CI lint rule that fails the build if `DEV_BYPASS_AUTH=true` appears in any non-`.gitignore`-d file
**Relevant Files:**
- `platform/scripts/` (multiple .sh files)
- `pmaas-secret-patch.json`
- `onboarding-agent/.env.local`
- `platform/gitops/tekton/pipeline-build.yaml` (add secret-scan task here)
**Status:** [ ] pending

---

#### P1-T2: Security Hardening — Authentication and Transport
**Intent:** Close all High-severity auth and transport security findings without changing
domain logic or service boundaries.
**Expected Outcomes:**
- EvalOS database pool validates TLS certificates
- WhatsApp webhook validates HMAC-SHA256 on every POST
- FORD membership API uses HMAC-SHA256 for all identifier tokens
- OTP stored in Redis with TTL, not in a SQL column
- Voice TTS enforces Bearer auth when `VOICE_API_KEY` is set
**Todo:**
- [ ] Set `ssl: { rejectUnauthorized: true }` in `platform/evalos/web/src/lib/db.ts`; coordinate CA cert mount with Crunchy operator
- [ ] Implement `X-Hub-Signature-256` HMAC-SHA256 validation on `POST /api/webhook/whatsapp` in `platform/engage/web/src/app/api/webhook/whatsapp/route.ts`
- [ ] Replace `hashlib.sha256` with `hmac.new(MEMBER_HMAC_SECRET, ...)` in `platform/ford/api/main.py`; add `MEMBER_HMAC_SECRET` to OpenBao at `i3/ford/`
- [ ] Deploy Redis in `i3-data` or `i3-admissions` namespace; replace OTP storage from `flagged_reason` column to `redis.setex(f"otp:{phone_hash}", 600, otp_hash)` in `platform/ford/api/main.py`
- [ ] Add OTP attempt rate limiting (max 5 attempts per 10-minute window) to `/api/v1/members/verify-otp`
- [ ] Replace OTP timing-vulnerable `!=` check with `hmac.compare_digest()`
- [ ] Validate `agent_id` format (e.g., UUID or alphanumeric pattern) in `platform/ford/api/main.py` to prevent velocity-cap bypass via cycling
- [ ] Add `helmet()` middleware to `onboarding-agent/src/server.ts`; include CSP, X-Frame-Options, HSTS
- [ ] Remove `DEV_BYPASS_AUTH` check from `keycloak-auth.ts` or ensure it only reads from a strictly `.gitignore`-d file
**Relevant Files:**
- `platform/evalos/web/src/lib/db.ts`
- `platform/engage/web/src/app/api/webhook/whatsapp/route.ts`
- `platform/ford/api/main.py`
- `onboarding-agent/src/security/keycloak-auth.ts`
- `onboarding-agent/src/server.ts`
**Status:** [ ] pending

---

#### P1-T3: Synchronous Blocking and Resource Leak Fixes
**Intent:** Fix all Critical runtime patterns that cause resource exhaustion or service
instability under load, before scaling or decoupling work begins.
**Expected Outcomes:**
- Kafka consumers use a startup-time asyncpg connection pool (not per-message connections)
- All asyncpg `connect()` calls are wrapped in `try/finally` blocks
- `planStore` Map in onboarding-agent is backed by Redis for HPA safety
- `_pending` confirmation dict in MCP connectors is backed by Redis
- `Promise.all` in skills-assessor wraps each subagent in individual try/catch
- WebSocket stream generator is cancelled when the client disconnects
**Todo:**
- [ ] Refactor `platform/engage/consumers/kafka_consumers.py`: initialize a single `asyncpg.Pool` at startup; share it across all consumer threads; remove per-message `asyncio.new_event_loop()` and `asyncio.connect()` calls
- [ ] Add `try/finally` blocks to all `asyncpg.connect()` call sites in `platform/ford/api/main.py` and `platform/talent/api/main.py` that currently lack them (lines 206–218 ford, lines 90–95 and 129–154 talent)
- [ ] Replace in-memory `planStore` Map in `onboarding-agent/src/server.ts` with Redis `GET/SET/DEL` calls using `planId` as key and a 2-hour TTL
- [ ] Replace in-memory `_pending` dict in `platform/admissions/mcp/mcp_connectors.py` with Redis `SETEX`/`GET`/`DEL` calls using the token UUID as key and 300s TTL
- [ ] Wrap each `plan.scanner.run(input)` call in `onboarding-agent/src/orchestrator/skills-assessor.ts` in an individual `Promise.allSettled` entry (or explicit try/catch) so one subagent failure returns empty findings rather than rejecting the entire assessment
- [ ] Add WebSocket cancellation in `platform/admissions/admissions_agent.py`: on `WebSocketDisconnect`, cancel the `stream_llm` generator and close the httpx response
- [ ] Add `asyncio.wait_for(..., timeout=10.0)` around all ChromaDB `run_in_executor` calls in `platform/pmaas/agents/campaign_agent.py` and `platform/admissions/admissions_agent.py`
- [ ] Add a concurrent VM semaphore (e.g., `asyncio.Semaphore(8)`) in `platform/evalos/sandbox_daemon.py` to cap simultaneous Firecracker processes
**Relevant Files:**
- `platform/engage/consumers/kafka_consumers.py`
- `platform/ford/api/main.py`
- `platform/talent/api/main.py`
- `onboarding-agent/src/server.ts`
- `platform/admissions/mcp/mcp_connectors.py`
- `onboarding-agent/src/orchestrator/skills-assessor.ts`
- `platform/admissions/admissions_agent.py`
- `platform/pmaas/agents/campaign_agent.py`
- `platform/evalos/sandbox_daemon.py`
**Status:** [ ] pending

---

#### P1-T4: Input Validation and Type Safety Hardening
**Intent:** Close all High-severity unvalidated input paths and `any`-type casts
that bypass TypeScript and Pydantic guarantees.
**Expected Outcomes:**
- All Kafka message payloads are validated against Pydantic models before processing
- All external API response casts in ingestion pipeline use runtime Zod validation
- LLM response key access is guarded against non-standard shapes
- Dynamic SQL query string in talent API is replaced with explicit parameterised clauses
- Lobster Trap Python version updated to 12 patterns (matching TypeScript version)
**Todo:**
- [ ] Define Pydantic `EmailEvent`, `SmsEvent`, `AiPersonaliseJob` models in `platform/engage/consumers/kafka_consumers.py`; parse every `msg.value` through these models before accessing fields
- [ ] Add Zod `.safeParse()` runtime validation to `(await resp.json()) as ExamDomain[]` in `onboarding-agent/src/ingestion/evalos.ts` and to the Directus response in `curriculum.ts`
- [ ] Wrap `r.json()["choices"][0]["message"]["content"]` in `platform/talent/api/main.py` and `platform/engage/consumers/kafka_consumers.py` in a helper function that validates the OpenAI response shape before key access
- [ ] Replace the f-string dynamic SQL pattern `query += f" AND c.location ILIKE ${ len(params)}"` in `platform/talent/api/main.py` with an explicit parameterised clause list approach
- [ ] Add 3 missing Lobster Trap patterns to `platform/admissions/admissions_agent.py`: `prompt\s+injection`, `disregard\s+(all\s+)?previous`, `\bexfiltrate\b`
- [ ] Add Lobster Trap (or equivalent) to `platform/pmaas/agents/campaign_agent.py` prompt assembly (all user-controlled fields: `ward_name`, `key_message`, `prompt`)
- [ ] Add `le=100` constraint to `MatchRequest.top_k` field in `platform/talent/api/main.py`
- [ ] Add `max_length` constraints to `MemberRegister.national_id` and `MemberRegister.phone` in `platform/ford/api/main.py`
**Relevant Files:**
- `platform/engage/consumers/kafka_consumers.py`
- `onboarding-agent/src/ingestion/evalos.ts`
- `onboarding-agent/src/ingestion/curriculum.ts`
- `platform/talent/api/main.py`
- `platform/admissions/admissions_agent.py`
- `platform/pmaas/agents/campaign_agent.py`
- `platform/ford/api/main.py`
**Status:** [ ] pending

---

#### P1-T5: Observability Foundation
**Intent:** Establish end-to-end observability — from HTTP request through every LLM call —
so that Phase 2 domain boundary changes can be validated against latency and cost baselines.
**Expected Outcomes:**
- Prometheus has at least 10 alerting rules covering critical thresholds
- Grafana is a StatefulSet with PVC (dashboards survive pod restarts)
- OpenTelemetry trace context propagates from every service entry point through LLM calls
- Langfuse receives traces tagged with `service_name`, `tenant_id`, `agent_id`
- Kafka consumer lag, LiteLLM queue depth, and PostgreSQL connection pool utilisation are monitored
**Todo:**
- [ ] Add PrometheusRule CRD to `platform/monitoring/prometheus-stack.yaml` with alerts for: CPU > 80%, memory > 85%, LiteLLM queue depth > 20, Kafka consumer lag > 1000, PostgreSQL connection pool > 80%, pod restart > 3 in 10 minutes
- [ ] Convert Grafana Deployment to StatefulSet with 5Gi PVC; inject admin password from OpenBao (remove plaintext env var `i3-grafana-admin`)
- [ ] Add Alertmanager Deployment to `platform/monitoring/` with Slack webhook route for P1/P2 alerts
- [ ] Add `opentelemetry-sdk` to all Python FastAPI services (`platform/admissions/`, `platform/ford/`, `platform/talent/`, `platform/pmaas/agents/`); instrument at request entry, LLM call, ChromaDB query, and DB write
- [ ] Add OpenTelemetry middleware to `onboarding-agent/src/server.ts`; propagate trace context through subagent `Promise.all` calls and granite-heavy synthesis call
- [ ] Update LiteLLM config in `platform/model-gateway/litellm/litellm-config-oss.yaml` to fix Langfuse host from `i3-ott` to `i3-model-gateway` namespace
- [ ] Add `tenant_id` and `agent_id` as Langfuse metadata fields on every LLM call in all agent services
- [ ] Add per-invocation token cost attribution to every `llm_chat()` helper in Python agents
**Relevant Files:**
- `platform/monitoring/prometheus-stack.yaml`
- `platform/model-gateway/litellm/litellm-config-oss.yaml`
- `platform/admissions/admissions_agent.py`
- `platform/ford/api/main.py`
- `platform/talent/api/main.py`
- `platform/pmaas/agents/campaign_agent.py`
- `onboarding-agent/src/server.ts`
**Status:** [ ] pending

---

#### P1-T6: Automated Test Harness
**Intent:** Establish automated test gates that run on every push to `main`, so that
Phase 2 domain boundary changes cannot silently regress existing behaviour.
**Expected Outcomes:**
- Tekton pipeline includes a dedicated `test` stage before `build`
- RAGAS evaluation datasets expanded from 3 questions to 30+ per agent
- Locust load tests are parameterised and run as scheduled Tekton PipelineRuns
- Promptfoo red-team runs in CI with exit-code gating on injection pass rate
- All `asyncpg` resource leak fixes (P1-T3) are covered by unit tests
**Todo:**
- [ ] Add `test` Task to `platform/gitops/tekton/pipeline-build.yaml` that runs `npm run typecheck && npm test` for Node services and `pytest` for Python services; gate `build-push` on test pass
- [ ] Expand `platform/testing/testing.py` RAGAS dataset: add 30 questions for admissions agent covering programme details, entry requirements, fees, scholarships, deferrals; update faithfulness threshold to 0.80, relevancy to 0.75
- [ ] Add RAGAS dataset for PMaaS campaign agent covering ward analysis, briefing quality, content generation for WhatsApp/social/voice
- [ ] Add scheduled Tekton PipelineRun (CronJob pattern) for Locust load test against staging; fail if p95 latency > SLO (200ms NBA, 3s plan generation)
- [ ] Extend promptfoo config to include OWASP LLM Top 10 vectors for all agents (not only admissions): campaign agent, onboarding agent, talent matching
- [ ] Write unit tests for connection pool lifecycle (startup pool creation, message processing reuse, graceful shutdown) in Kafka consumers
- [ ] Add integration test for the 2-stage MCP confirmation gate (prepare → confirm within TTL; prepare → confirm after TTL expiry should fail)
**Relevant Files:**
- `platform/gitops/tekton/pipeline-build.yaml`
- `platform/testing/testing.py`
- `onboarding-agent/src/orchestrator/` (tests alongside source)
**Status:** [ ] pending

---

### Phase 1 — Exit Criteria

All of the following must be true before Phase 2 begins:

- [ ] Zero Critical findings open in the security audit (P1-T1 and P1-T2 complete and verified)
- [ ] Zero High findings open related to resource leaks or blocking I/O (P1-T3 complete)
- [ ] All Kafka consumers use a connection pool; confirmed by load test showing no PG connection exhaustion at 100 concurrent messages
- [ ] Prometheus alerting rules are live and have fired at least one test alert successfully
- [ ] Grafana is a StatefulSet with persistent dashboards
- [ ] Tekton pipeline has a `test` stage that blocks `build-push` on failure
- [ ] OTel traces visible in Langfuse for at least one end-to-end plan-generation request
- [ ] RAGAS faithfulness ≥ 0.80 and relevancy ≥ 0.75 passing in CI for all three evaluated agents
- [ ] `gitleaks` or `trufflehog` is a blocking Tekton stage and has zero findings on current HEAD
- [ ] `.env.local` is not tracked by git

---

---

## Phase 2: Domain Decoupling
### Breaking Monolith Boundaries · API Abstraction · DDD Bounded Contexts

**Goal:** Extract cross-cutting concerns into dedicated services, establish clean domain
boundaries aligned with the Enhancement 3 nine-plane architecture, and introduce the
Agent Mesh foundation (registry, MCP Tool Gateway, decision log).

---

### Phase 2 — Entry Criteria

- [ ] All Phase 1 exit criteria are met (verified by CI green gate)
- [ ] OpenTelemetry baseline latency profiles are captured for all existing endpoints
- [ ] Redis is deployed and reachable (introduced in Phase 1 for OTP and plan store)
- [ ] Architecture Decision Record (ADR) template is in place at `platform/docs/adr/`

---

### Phase 2 — Sub-Tasks

#### P2-T1: Extract Consent Service (Cross-Cutting — All Domains)
**Intent:** Centralise all DPA 2019 / GDPR-equivalent consent enforcement into a single
microservice, consumed by every service that touches personal data. This is the single
highest-risk cross-cutting concern identified across all Enhancement 3 guides.
**Expected Outcomes:**
- A new `consent-service` FastAPI microservice owns the `consent_records` table
- Every outbound message path (Engage campaigns, FORD OTP, SIT enrollment) queries consent before dispatch
- Consent decisions are logged to an immutable append-only audit table
- The `consent` boolean in `MemberRegister` is replaced by a proper consent record with purpose, channel, and timestamp
**Todo:**
- [ ] Create `platform/consent/` with FastAPI service exposing: `POST /consent` (record consent), `GET /consent/{subject_id}?channel={}&purpose={}` (check consent), `DELETE /consent/{subject_id}` (erasure request), `GET /consent/{subject_id}/audit` (audit trail)
- [ ] Create `consent_records` and `consent_audit` tables with `tenant_id`, `subject_id_hash`, `channel`, `purpose`, `status`, `recorded_at`, `source`, `expiry`, `version`
- [ ] Add consent check call to `platform/engage/web/src/app/api/campaigns/send/route.ts` before email dispatch
- [ ] Add consent check call to `platform/ford/api/main.py` `/register` endpoint (replace boolean `consent` field with consent service call)
- [ ] Add consent check call to `platform/sit/api/main.py` `/learners` enrollment
- [ ] Deploy consent-service in new `i3-consent` namespace; add to ArgoCD wave structure (Wave 1.5 between operators and model-gateway)
- [ ] Write ADR: `platform/docs/adr/ADR-001-consent-service-extraction.md`
**Relevant Context:**
- Enhancement 3 PMC guide §5 (Consent as Central Policy Service)
- Enhancement 3 PMaaS Consolidated guide §8 (Identity, Authentication, Consent)
- `platform/ford/api/main.py:28-35` (current consent as boolean)
- `platform/engage/web/src/app/api/campaigns/send/route.ts` (no consent check today)
**Status:** [ ] pending

---

#### P2-T2: Introduce Agent Registry and Decision Log
**Intent:** Build the foundational Agent Mesh control plane — agent registry with lifecycle
states and a structured decision log — that all existing agents (Nuru/admissions, Dawa/PMaaS,
onboarding subagents) will register into. This is a prerequisite for MCP Tool Gateway and
autonomy tier enforcement.
**Expected Outcomes:**
- A new `agent-registry` service owns agent manifests and lifecycle state machine
- Every agent call emits a structured decision log record
- Progressive autonomy tier (L0–L3) is declared per agent; L0/L1 is the only permitted tier at Phase 2 launch
- An `agent_decision_log` table exists and receives entries from all agents
**Todo:**
- [ ] Create `platform/agent-registry/` with FastAPI service exposing: `GET /agents` (list), `POST /agents` (register), `GET /agents/{agent_id}` (manifest), `PATCH /agents/{agent_id}/state` (lifecycle transition), `GET /agents/{agent_id}/decisions` (audit)
- [ ] Create `agent_registry` and `agent_decision_log` tables (use schema from Enhancement 3 Agentic AI Platform guide §14)
- [ ] Define YAML agent manifests for: `admissions-agent`, `pmaas-campaign-agent`, `onboarding-planner`, `onboarding-subagent-infra`, `onboarding-subagent-ailab`, `onboarding-subagent-backend`; include `autonomy_tier`, `allowed_tools`, `forbidden_tools`, `cost_budget_tokens`, `guardrail_policy`
- [ ] Add decision log emission to `platform/admissions/admissions_agent.py` on every LLM call: `agent_id`, `session_id`, `tenant_id`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `outcome`, `timestamp`
- [ ] Add decision log emission to `platform/pmaas/agents/campaign_agent.py` on every endpoint
- [ ] Add decision log emission to `onboarding-agent/src/orchestrator/planner.ts` and `base-scan.ts`
- [ ] Deploy agent-registry in `i3-agent-mesh` namespace (new namespace, Wave 4.5 in ArgoCD)
- [ ] Write ADR: `platform/docs/adr/ADR-002-agent-registry-decision-log.md`
**Relevant Context:**
- Enhancement 3 Agentic AI Platform guide §4.1 (Agent Registry), §14 (Decision Log Schema), §15 (Autonomy Tiers)
- Enhancement 3 E³ guide P11 (Progressive Autonomy), P3 (Agents Propose, Policy Disposes)
- `platform/pmaas/agents/campaign_agent.py` (current agent — no registry)
- `onboarding-agent/src/orchestrator/subagents/base-scan.ts` (current subagents — no registry)
**Status:** [ ] pending

---

#### P2-T3: MCP Tool Gateway
**Intent:** Wrap every external integration (ChromaDB queries, Kafka produces, PostgreSQL writes,
SMS/email dispatch) as typed MCP tools with declared side-effect class and risk tier.
Agents call tools through the gateway; the gateway enforces the agent manifest's
`allowed_tools`/`forbidden_tools` and logs every tool invocation.
**Expected Outcomes:**
- A new `mcp-gateway` service exposes all platform tools as MCP-compatible endpoints
- All LLM agents call tools through the gateway, not directly
- Tool calls are blocked if the calling agent's manifest does not list the tool in `allowed_tools`
- Every tool call is logged with: agent_id, tool_name, input_hash, output_class, duration_ms, risk_tier
**Todo:**
- [ ] Create `platform/mcp-gateway/` with FastAPI service; implement tool contract schema: `name`, `description`, `version`, `tenant_scope`, `read_write`, `side_effect_class`, `risk_tier`, `rate_limit`, `timeout`, `idempotency_key`, `audit_required`
- [ ] Migrate `platform/admissions/mcp/mcp_connectors.py` tools (Odoo CRM, Google Calendar, n8n, Directus) into the MCP gateway with proper risk-tier declarations (Odoo write = Tier 2, Calendar book = Tier 2, Directus write = Tier 1)
- [ ] Register ChromaDB search as a Tier 0 (read-only) MCP tool
- [ ] Register LiteLLM inference as a Tier 1 (low-risk) MCP tool with cost_budget enforcement
- [ ] Register Kafka produce as a Tier 2 (customer-facing) MCP tool requiring policy check
- [ ] Register PostgreSQL write operations as Tier 2–3 tools depending on table
- [ ] Refactor `platform/admissions/admissions_agent.py` to call tools via MCP gateway instead of direct service calls
- [ ] Refactor `platform/pmaas/agents/campaign_agent.py` to call ChromaDB and LiteLLM via MCP gateway
- [ ] Deploy mcp-gateway in `i3-agent-mesh` namespace; update NetworkPolicies to allow agent namespaces to reach mcp-gateway on port 8100
- [ ] Write ADR: `platform/docs/adr/ADR-003-mcp-tool-gateway.md`
**Relevant Context:**
- Enhancement 3 Agentic AI Platform guide §7 (MCP Tool Gateway spec)
- Enhancement 3 E³ guide P4 (Open protocols at every seam), P9 (Small surface, deep contracts)
- Enhancement 3 PMC guide §7.1 (Tool Permission Model — Risk Tiers)
- `platform/admissions/mcp/mcp_connectors.py` (current direct integrations)
**Status:** [ ] pending

---

#### P2-T4: Tenant Isolation — tenant_id on All Domain Tables
**Intent:** Enforce architectural principle P7 (Multi-tenant from line one) across all
domain services that currently lack `tenant_id` on their core tables.
**Expected Outcomes:**
- `engage_db`: `email_campaigns`, `contacts`, `contact_lists`, `inbound_messages` all have `tenant_id UUID NOT NULL`
- `pmaas_db`: `campaigns`, `voters`, `ward_targets` all have `tenant_id UUID NOT NULL`
- PostgreSQL Row-Level Security (RLS) policies exist on all multi-tenant tables
- Every API route handler passes `tenant_id` (derived from JWT `realm_access.roles` or OIDC claim) into query context
**Todo:**
- [ ] Write migration `platform/engage/web/migrations/002_add_tenant_id.sql`: ADD COLUMN `tenant_id UUID NOT NULL DEFAULT gen_random_uuid()` to all Engage tables; add RLS policy; add index on `(tenant_id, created_at DESC)`
- [ ] Write migration `platform/pmaas/web/migrations/002_add_tenant_id.sql`: same for PMaaS tables
- [ ] Update all Engage `route.ts` API handlers to extract `tenant_id` from NextAuth session and pass to pool queries
- [ ] Update all PMaaS `route.ts` API handlers similarly
- [ ] Update `platform/ford/api/main.py` to include `tenant_id` on `members_pii` and `agent_velocity` tables
- [ ] Backfill existing rows with a default `tenant_id` value representing the i3 production tenant
- [ ] Write ADR: `platform/docs/adr/ADR-004-tenant-isolation.md`
**Relevant Context:**
- Enhancement 3 E³ guide P7 (Multi-tenant from line one)
- Enhancement 3 PMC guide §14.2 (Tenant isolation — dedicated OpenShift namespace)
- `platform/engage/web/src/app/api/campaigns/route.ts` (no tenant_id today)
- `platform/engage/web/migrations/001_init.sql` (current schema)
**Status:** [ ] pending

---

#### P2-T5: Domain Service Boundary Extraction — Credential and Grading Services
**Intent:** Extract two of the highest-value cross-domain concerns (credential issuance and
exam grading) into dedicated microservices with clean APIs, so that EvalOS, SIT, and FORD
can consume them without tight coupling.
**Expected Outcomes:**
- A `credential-service` owns all W3C VC issuance, QR token generation, and public verification
- A `grading-service` owns all exam scoring, domain breakdown calculation, and pass/fail determination
- EvalOS submit route delegates to grading-service; SIT delegates credential issuance to credential-service
- The `code_submissions.plagiarism_score` field is populated by grading-service
**Todo:**
- [ ] Create `platform/credential/` with FastAPI service: `POST /credentials` (issue), `GET /credentials/{qr_token}/verify` (public, no auth), `POST /credentials/revoke`, `GET /credentials/{learner_id}` (list); store W3C VC JSON; prepare Hyperledger Fabric anchor slot (Phase 3)
- [ ] Create `platform/grading/` with FastAPI service: `POST /grade` (input: question_snapshot, answers → output: score, domain_breakdown, passed, detailed_results); separate grading logic from `platform/evalos/web/src/app/api/exam/[examId]/submit/route.ts`
- [ ] Refactor EvalOS submit route to call grading-service and write result back
- [ ] Refactor SIT credential issuance to call credential-service instead of inline generation
- [ ] Replace `Math.random()` Fisher-Yates shuffle in EvalOS exam start with `crypto.getRandomValues()`
- [ ] Deploy credential-service and grading-service in `i3-evalos` namespace (same namespace, separate pods)
- [ ] Write ADR: `platform/docs/adr/ADR-005-credential-grading-extraction.md`
**Relevant Context:**
- Enhancement 3 E³ guide §8 (Trust & Evidence Plane), P6 (Evidence by Construction)
- Enhancement 3 PMaaS Consolidated guide §8 (Identity, Authentication, Ballot Secrecy)
- `platform/evalos/web/src/app/api/exam/[examId]/submit/route.ts` (current inline grading)
- `platform/sit/api/main.py` lines 142–196 (current inline credential issuance)
**Status:** [ ] pending

---

#### P2-T6: API Gateway and GraphQL BFF Introduction
**Intent:** Introduce an API composition layer (L2 in the 8-layer model) that handles
tenant resolution, rate limiting, and request routing, removing these concerns from
individual services.
**Expected Outcomes:**
- Kong (or IBM API Connect) is deployed as the cluster API gateway
- All external-facing routes are accessible via `api.i3technologies.co.ke` with JWT validation at the gateway
- Internal service-to-service calls use cluster-internal DNS (not gateway)
- Rate limiting is enforced per-tenant at the gateway layer, not in application code
**Todo:**
- [ ] Define Kong Deployment/Route CRDs in `platform/deploy/api-gateway/`; configure in ArgoCD as Wave 1.8
- [ ] Declare consumer plugins: JWT validation against Keycloak JWKS, rate-limit (100 RPM default per tenant, 10 RPM for LLM endpoints), request-size limit (512KB default)
- [ ] Register all externally-facing routes: Engage web API, EvalOS web API, Admissions chat, PMaaS web API, Onboarding agent API, Voice TTS
- [ ] Remove per-service CORS `allow_origins=["*"]` from `platform/admissions/admissions_agent.py`, `platform/ford/api/main.py`, `platform/talent/api/main.py`, `platform/pmaas/agents/campaign_agent.py`, `platform/voice/tts/tts_service.py`; replace with gateway-level CORS policy scoped to known origins
- [ ] Add authentication to admissions-agent and MCP connectors via gateway JWT plugin (resolves open H-2 finding)
- [ ] Write ADR: `platform/docs/adr/ADR-006-api-gateway.md`
**Relevant Context:**
- Enhancement 3 E³ guide L2 (Edge & Gateway layer)
- Enhancement 3 PMC guide §13 (Technology Stack — API surface: REST, GraphQL, Webhooks)
- `platform/admissions/admissions_agent.py` (currently fully unauthenticated)
- `platform/admissions/mcp/mcp_connectors.py` (currently fully unauthenticated)
**Status:** [ ] pending

---

### Phase 2 — Exit Criteria

All of the following must be true before Phase 3 begins:

- [ ] Consent Service is live in `i3-consent` namespace; all three consuming services (Engage, FORD, SIT) check consent before PII-touching operations
- [ ] Agent Registry contains manifests for all 6 existing agents; decision log is receiving entries
- [ ] MCP Tool Gateway is live; Admissions agent and PMaaS campaign agent route tool calls through it
- [ ] `tenant_id` migration is applied to `engage_db` and `pmaas_db`; RLS policies are active
- [ ] Credential Service and Grading Service are deployed and consumed by EvalOS and SIT
- [ ] API Gateway is live; all five previously-unauthenticated services now require valid JWT at gateway
- [ ] All ADRs (ADR-001 through ADR-006) are written, reviewed, and merged
- [ ] No regression in RAGAS scores (faithfulness and relevancy must remain ≥ Phase 1 exit thresholds)
- [ ] Existing Locust p95 latency baselines are not exceeded by more than 15%
- [ ] Zero new Critical or High findings introduced in Phase 2 code

---

---

## Phase 3: Runtime Optimization
### Caching · Async Queues · CI/CD Automated Gates · Agent Mesh Completion

**Goal:** Harden the platform to production-scale: introduce semantic caching for LLM calls,
implement full async queue patterns for all AI inference paths, complete the Hyperledger Fabric
integration for FORD, and close out the automated CI/CD gate pipeline so that every
production deployment is gated by security scan, load test, RAGAS evaluation, and red-team.

---

### Phase 3 — Entry Criteria

- [ ] All Phase 2 exit criteria are met (verified by CI green gate)
- [ ] Prometheus alerting rules from Phase 1 have been in production for at least one sprint with no false-positive storm
- [ ] Agent Registry has processed real production traffic and decision log contains at least 1,000 entries
- [ ] A staging environment exists that mirrors production (same ArgoCD waves, separate namespace prefix `i3-staging-*`)

---

### Phase 3 — Sub-Tasks

#### P3-T1: Semantic Caching and Token Budget Enforcement
**Intent:** Implement semantic caching for repeated or near-identical LLM queries, and enforce
per-invocation token budgets as declared in agent manifests, reducing model gateway cost and
improving tail latency.
**Expected Outcomes:**
- LiteLLM proxy has semantic caching enabled backed by Redis
- Every agent invocation carries a `cost_budget` header that LiteLLM enforces
- Token usage per tenant per day is tracked and alerted when approaching limit
- Repeated FAQ queries in admissions agent hit cache instead of model; p95 latency drops ≥ 40%
**Todo:**
- [ ] Enable LiteLLM semantic caching in `platform/model-gateway/litellm/litellm-config-oss.yaml`: add `cache: { type: redis, host: redis-service.i3-data.svc, ttl: 3600 }`; use existing Redis deployed in Phase 1
- [ ] Add per-tenant daily token budget as a LiteLLM virtual key configuration; expose budget management via Agent Registry API
- [ ] Add `X-Cost-Budget-Tokens` header to every LiteLLM call from all agents; wire this to the `cost_budget_tokens` field in the agent manifest
- [ ] Add Prometheus alert: `litellm_token_usage_daily{tenant_id}` > 80% of tenant budget
- [ ] Instrument cache hit/miss rate as a Grafana dashboard panel alongside p50/p95 latency
**Relevant Context:**
- Enhancement 3 Agentic AI Platform guide §20 (Cost Engineering), §7.4 (Safety & Cost Controls)
- Enhancement 3 E³ guide (Semantic caching, small-model routing, tenant caps are mandatory)
- `platform/model-gateway/litellm/litellm-config-oss.yaml` (current config, no caching)
**Status:** [ ] pending

---

#### P3-T2: Full Async Queue Pattern for AI Inference Paths
**Intent:** Move all non-interactive AI inference (campaign personalisation, briefing generation,
batch content generation) off the synchronous HTTP request path onto Kafka-backed async workers,
so that HTTP endpoints return immediately with a job ID and the result is delivered via webhook
or polling.
**Expected Outcomes:**
- `POST /api/campaigns/send` returns immediately with `{ job_id, status: "queued" }` instead of blocking
- `POST /briefing/generate` in PMaaS returns immediately; result delivered via Kafka consumer to a polling endpoint
- Campaign content generation worker auto-scales via KEDA on `engage.ai-personalize` topic depth
- Failed AI jobs are routed to a dead-letter topic `engage.ai-personalize.dlq` with retry metadata
**Todo:**
- [ ] Refactor `platform/engage/web/src/app/api/campaigns/send/route.ts`: produce a `SendJobRequest` Kafka message to `engage.campaign-trigger` and return `{ job_id }` immediately; implement `GET /api/campaigns/send/{job_id}` polling endpoint
- [ ] Refactor PMaaS briefing generation: produce to `pmaas.briefing-requests` topic; create async consumer that calls campaign agent and writes result to PostgreSQL; expose `GET /api/briefing/{job_id}` polling endpoint
- [ ] Add dead-letter topic `engage.ai-personalize.dlq` in Strimzi Kafka config; update consumer to route to DLQ after 3 retries
- [ ] Add KEDA ScaledObject for `engage.campaign-trigger` consumer: scale on topic partition lag (min 1, max 6)
- [ ] Update `platform/engage/consumers/kafka_consumers.py` to use `enable_auto_commit=False` and manually commit offset only after successful DB write (fixes current at-most-once delivery)
**Relevant Context:**
- Enhancement 3 Agentic AI Platform guide P2 (Events are the spine), §22 (Kafka Event Model)
- `platform/engage/consumers/kafka_consumers.py` (current sync blocking consumer)
- `platform/engage/web/src/app/api/campaigns/send/route.ts` (current blocking send)
- `platform/model-gateway/keda/keda-scaled-objects.yaml` (existing KEDA patterns)
**Status:** [ ] pending

---

#### P3-T3: Hyperledger Fabric Integration (FORD IEBC Deadline)
**Intent:** Complete the blockchain-backed membership ledger integration that is a hard
requirement for FORD-Asili ahead of the IEBC 16 March 2027 deadline. This is the only
Phase 3 task with an external hard deadline.
**Expected Outcomes:**
- A Hyperledger Fabric network with 3 peers is deployed on OpenShift
- `MembershipRegistry` chaincode is deployed and callable from `platform/ford/api/main.py`
- Every verified member registration emits a Fabric transaction
- A public verification endpoint returns membership hash + status without exposing PII
- Two full pilot runs are completed before 16 March 2027
**Todo:**
- [ ] Deploy Hyperledger Fabric on OpenShift using Fabric Operator; create `ford-channel` with 3 peer organisations (FORD-Asili, ORPP-observer, Audit-observer)
- [ ] Implement `MembershipRegistry` chaincode (Go): `RegisterMember(id_hash, phone_hash, ward_code, timestamp)`, `VerifyMember(id_hash)`, `GetWardCount(ward_code)`, `GetAgentDutyCount(agent_id)`
- [ ] Complete the TODO at `platform/ford/api/main.py:177`: replace comment with actual Fabric SDK call to `MembershipRegistry.RegisterMember`
- [ ] Implement USSD bridge using Africa's Talking USSD API (`*509#`-class) that routes to the `/api/v1/members/register` endpoint; rural members should not require a smartphone
- [ ] Add public verification endpoint `GET /api/v1/members/verify/{public_token}` that queries Fabric only (no PII exposure)
- [ ] Run Pilot 1 (internal) and Pilot 2 (ward-level) before 17 March 2027 primaries window
- [ ] Write ADR: `platform/docs/adr/ADR-007-hyperledger-fabric-membership-ledger.md`
**Relevant Context:**
- Enhancement 3 FORD-Asili guide §5 (Blockchain Network Design), §6 (Identity/Ballot Secrecy), §14 (IEBC-dated Roadmap)
- Enhancement 3 PMaaS Consolidated guide §6 (Blockchain System of Record), Appendix A (Chaincode Reference)
- `platform/ford/api/main.py:177` (TODO: Fabric SDK call)
- IEBC hard deadline: 16 March 2027 (membership list submission)
**Status:** [ ] pending

---

#### P3-T4: CI/CD Automated Production Gates
**Intent:** Ensure that no code reaches production without passing all four automated
quality gates: secret scan, container vulnerability scan, RAGAS quality gate, and
red-team injection resistance gate.
**Expected Outcomes:**
- Every push to `main` runs all four gates in sequence; any failure blocks deployment
- RAGAS gate fails the pipeline if faithfulness drops below 0.80 for any evaluated agent
- Promptfoo red-team gate fails if any injection vector produces a blocked pattern response
- Trivy gate fails on any CRITICAL CVE (already in place) but is extended to fail on HIGH CVEs with a fix available
- All gate results are published as Tekton PipelineRun annotations visible in ArgoCD
**Todo:**
- [ ] Add `secret-scan` Task to Tekton pipeline (before all other tasks): run `trufflehog filesystem .` on workspace; fail pipeline on any finding
- [ ] Extend Trivy severity filter from `HIGH,CRITICAL` to include `MEDIUM` with `--exit-code 0` (warning only) while keeping `HIGH,CRITICAL` at `--exit-code 1`
- [ ] Add `ragas-eval` Task to Tekton pipeline (after deploy to staging, before promote to production): call `python platform/testing/testing.py --ragas --ragas-onboarding`; fail if any score below threshold
- [ ] Add `promptfoo-redteam` Task to Tekton pipeline (parallel with ragas-eval): run expanded 20-vector red-team suite for all three agents; fail if pass rate < 100%
- [ ] Add Argo CD pre-sync hook to run smoke test (health check + one representative request) before marking sync Complete
- [ ] Publish all gate results as Kubernetes Annotations on the PipelineRun object; expose via Grafana panel
**Relevant Context:**
- Enhancement 3 Agentic AI Platform guide §12 (Evaluation Framework — 5 layers)
- Enhancement 3 PMC guide §20 (Production Readiness Checklist)
- `platform/gitops/tekton/pipeline-build.yaml` (current pipeline, add tasks here)
- `platform/testing/testing.py` (RAGAS and Locust — extend here)
**Status:** [ ] pending

---

#### P3-T5: PWA and Offline-Tolerant Client for Engage and PMaaS
**Intent:** Implement architectural principle P from the E³ guide: East African users experience
intermittent bandwidth. The Engage and PMaaS web clients must be PWAs with offline-tolerant
read paths and queued writes.
**Expected Outcomes:**
- `platform/engage/web` and `platform/pmaas/web` are PWAs with service workers
- Campaign dashboard, contact list, and ward targeting views are readable when offline
- Write operations (create campaign, register voter) are queued in IndexedDB and synced when online
- App shell loads in < 2s on a 3G connection (Lighthouse PWA score ≥ 80)
**Todo:**
- [ ] Add `next-pwa` or `@ducanh2912/next-pwa` to `platform/engage/web` and `platform/pmaas/web`; configure service worker with network-first strategy for API routes and cache-first for static assets
- [ ] Implement offline queue for `POST /api/campaigns` and `POST /api/voters` using Background Sync API with IndexedDB backing store
- [ ] Add `manifest.json` with app name, icons, theme colour, and display mode `standalone`
- [ ] Add offline fallback page rendered from service worker cache
- [ ] Validate Lighthouse PWA score ≥ 80 as part of CI (use `lighthouse-ci`)
**Relevant Context:**
- Enhancement 3 E³ guide §2.3 Design Constraint 1 (Connectivity variance — MUST be PWA)
- Enhancement 3 SACP guide §3.1 (SACP Workspace — unified portal)
- `platform/engage/web/src/app/layout.tsx` (current Next.js entry point, no PWA)
**Status:** [ ] pending

---

### Phase 3 — Exit Criteria

All of the following must be true for the platform to be declared Phase 3 complete:

- [ ] LiteLLM semantic cache is live; cache hit rate ≥ 20% for admissions FAQ queries
- [ ] Campaign send and briefing generation are fully async; no endpoint blocks for > 500ms
- [ ] Dead-letter topic is live; no messages lost on consumer crash (verified by chaos test)
- [ ] FORD Fabric integration is live in staging; two pilot runs completed successfully
- [ ] USSD bridge is live and tested with Africa's Talking sandbox
- [ ] All four CI/CD gates (secret scan, Trivy, RAGAS, promptfoo) are blocking `main` merges
- [ ] RAGAS faithfulness ≥ 0.80 and relevancy ≥ 0.75 maintained across all agents
- [ ] Engage and PMaaS PWA Lighthouse score ≥ 80
- [ ] p95 latency for interactive endpoints (exam start, campaign create, chat): ≤ 3s
- [ ] p95 latency for NBA / consent decision: ≤ 200ms
- [ ] Zero open Critical or High security findings
- [ ] All ADRs (ADR-001 through ADR-007) are written, reviewed, and in `platform/docs/adr/`

---

---

## Appendix A — Domain Service Inventory

| Service | Bounded Context | Owning Namespace | Phase |
|---|---|---|---|
| consent-service | Consent & Privacy | i3-consent | Phase 2 |
| agent-registry | Agent Governance | i3-agent-mesh | Phase 2 |
| mcp-gateway | Tool Governance | i3-agent-mesh | Phase 2 |
| credential-service | Trust & Evidence | i3-evalos | Phase 2 |
| grading-service | Assessment Scoring | i3-evalos | Phase 2 |
| api-gateway (Kong) | Edge & Gateway | i3-gateway | Phase 2 |
| ford-api (updated) | Member Registration | i3-ford | Phase 1+2 |
| fabric-bridge | Membership Ledger | i3-ford | Phase 3 |
| admissions-agent | Academic Q&A | i3-admissions | Phase 1+2 |
| pmaas-campaign-agent | Campaign Intelligence | i3-pmaas | Phase 1+2+3 |
| engage-web | Campaign Delivery | i3-engage | Phase 1+2+3 |
| evalos-web | Assessment Delivery | i3-evalos | Phase 1+2 |
| talent-api | Candidate Matching | i3-talent | Phase 1+2 |
| sit-api | Enrollment Pipeline | i3-sit | Phase 2 |
| ott-pipeline | Media Processing | i3-ott | Phase 2 |
| smartlab-api | Content Authoring | i3-smartlab | Phase 2 |

## Appendix B — Architecture Decision Records Required

| ADR | Title | Phase |
|---|---|---|
| ADR-001 | Consent Service Extraction | Phase 2 |
| ADR-002 | Agent Registry and Decision Log | Phase 2 |
| ADR-003 | MCP Tool Gateway | Phase 2 |
| ADR-004 | Tenant Isolation Strategy | Phase 2 |
| ADR-005 | Credential and Grading Service Extraction | Phase 2 |
| ADR-006 | API Gateway Introduction | Phase 2 |
| ADR-007 | Hyperledger Fabric Membership Ledger | Phase 3 |

## Appendix C — Hard Constraint Reference

From Enhancement 3 guides and codebase audit, these constraints are non-negotiable:

1. **IBM Cloud credit balance must be verified** before Phase 1 begins (i3 PMC Risk #1)
2. **FORD Fabric integration must be live in staging by November 2026** (IEBC 16 March 2027 deadline — Phase 3)
3. **No agent autonomy promotion beyond L1 without evaluation evidence** (P11)
4. **tenant_id on every row, event, log line** (P7)
5. **Agents propose, policy disposes** — no agent takes a side-effecting action without going through MCP gateway and policy check (P3)
6. **solution-01 through solution-08 namespaces must never be touched** by any task in this plan
7. **HMAC-SHA256 with KMS secret** for all identifier tokens in FORD service (not SHA-256)
8. **`DEV_BYPASS_AUTH=true` must never reach staging or production** (enforced by CI lint gate from P1-T1)
