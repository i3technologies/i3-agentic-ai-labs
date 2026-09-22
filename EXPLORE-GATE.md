# EXPLORE-GATE.md
**i3 AI Platform — Explore Phase Exit Artefact**
Produced: 2026-09-22 | Author: Bob (Lead Architect Review)
Commit: `73d913a` | Branch: `main`

> This document is the mandatory gate artefact required before entering PLAN phase.
> It records current-state architecture, all dependency maps, security findings,
> and the recommended implementation sequence for Phase 2.

---

## 1. Current-State Architecture

### 1.1 Platform Overview
The i3 AI Platform is a polyglot, multi-tenant SaaS platform running on IBM Cloud
OpenShift 4.17 (cluster `i3-platform`, Frankfurt eu-de, 12 nodes). It comprises
7 product domains, each in an isolated OpenShift namespace, sharing a common
data layer, model gateway, and identity provider.

### 1.2 Namespace Inventory (25 active)

| Namespace | Purpose | Runtime |
|-----------|---------|---------|
| `i3-data` | PostgreSQL (Crunchy), Redis, SeaweedFS | StatefulSets |
| `i3-messaging` | Kafka KRaft (3-broker) | StatefulSet |
| `i3-security` | OpenBao (3-pod, initialized+unsealed) | StatefulSet |
| `i3-auth` | Keycloak 21 (CR: `i3-keycloak`, realm: `i3`) | StatefulSet |
| `i3-gitops` | Tekton Pipelines, ArgoCD | Deployments |
| `i3-model-gateway` | LiteLLM proxy, Ollama, Langfuse, KEDA | Deployments |
| `i3-ai-lab` | JupyterHub, ChromaDB, Open WebUI | StatefulSets |
| `i3-gateway` | Kong API Gateway | Deployment |
| `i3-consent` | Consent Service (stub — not yet live) | — |
| `i3-agent-mesh` | MCP Gateway (port 8100), Agent Registry (port 8200) | Deployments |
| `i3-evalos` | EvalOS Next.js, Zuri AI, grading service | Deployments |
| `i3-ott` | OvenMediaEngine streaming | StatefulSet |
| `i3-admissions` | Admissions Agent (FastAPI), ChromaDB, MCP connectors | Deployments |
| `i3-monitoring` | Prometheus, Grafana (1/1 Ready), Alertmanager | StatefulSets |
| `i3-ford` | FORD-Asili API, Fabric CA, CouchDB, orderer (crashed) | Mixed |
| `i3-engage` | Engage Next.js, Kafka consumers | Deployments |
| `i3-pmaas` | PMaaS Next.js, Campaign agent | Deployments |
| `i3-afroerp` | AfroERP (Frappe/ERPNext) | Deployment |
| `i3-voice` | TTS service (FastAPI) | Deployment |
| `i3-admissions` | (duplicate row — same as above) | — |
| `i3-onboarding` | Onboarding Agent (TypeScript/Express) | Deployment |

### 1.3 Service Inventory

| Service | Namespace | Language/Runtime | Port | Status |
|---------|-----------|-----------------|------|--------|
| Admissions Agent | i3-admissions | Python/FastAPI | 8000 | Running (chromadb bug) |
| MCP Gateway | i3-agent-mesh | Python/FastAPI | 8100 | Running |
| Agent Registry | i3-agent-mesh | Python/FastAPI | 8200 | Running |
| Consent Service | i3-consent | Python/FastAPI | 8000 | **NOT DEPLOYED** |
| LiteLLM Proxy | i3-model-gateway | Python/LiteLLM | 4000 | Running |
| Ollama | i3-model-gateway | Go | 11434 | Running |
| Langfuse | i3-model-gateway | Next.js | 3000 | Running |
| Engage Web | i3-engage | TypeScript/Next.js 15 | 3000 | Running |
| Engage Consumers | i3-engage | Python/asyncpg | — | Running |
| PMaaS Web | i3-pmaas | TypeScript/Next.js 15 | 3000 | Running |
| Campaign Agent | i3-pmaas | Python/FastAPI | 8080 | Running |
| EvalOS Web | i3-evalos | TypeScript/Next.js 15 | 3000 | Running |
| EvalOS Zuri | i3-evalos | Python/FastAPI | 8000 | Running |
| Onboarding Agent | i3-onboarding | TypeScript/Express | — | Running |
| FORD API | i3-ford | Python/FastAPI + Go | — | Running |
| Fabric Orderer | i3-ford | Hyperledger Fabric 2.5.9 | 7050 | **CrashLoopBackOff** |
| Fabric CA (ford) | i3-ford | Hyperledger Fabric CA | 7054 | Running |
| AfroERP | i3-afroerp | Python/Frappe | — | Running |
| Voice TTS | i3-voice | Python/FastAPI | — | Running |
| JupyterHub | i3-ai-lab | Python | 8000 | Running |

---

## 2. Dependency Map

### 2.1 Synchronous Dependencies

```
Browser/Client
    │
    ▼
Kong API Gateway (i3-gateway)
    │
    ├──► Keycloak (i3-auth) ──────────────── JWT validation on all services
    │
    ├──► Admissions Agent (i3-admissions)
    │        └──► LiteLLM Proxy (i3-model-gateway)
    │        └──► ChromaDB (i3-admissions)
    │        └──► MCP Gateway (i3-agent-mesh)
    │                └──► Agent Registry (i3-agent-mesh)
    │                └──► Consent Service (i3-consent) [NOT LIVE]
    │
    ├──► PMaaS Web (i3-pmaas)
    │        └──► LiteLLM Proxy
    │        └──► Campaign Agent (i3-pmaas)
    │        └──► PostgreSQL (i3-data)
    │
    ├──► Engage Web (i3-engage)
    │        └──► PostgreSQL (i3-data)
    │        └──► Brevo API [external]
    │
    ├──► EvalOS Web (i3-evalos)
    │        └──► PostgreSQL (i3-data)
    │        └──► LiteLLM Proxy
    │
    └──► FORD API (i3-ford)
             └──► PostgreSQL (i3-data)
             └──► Fabric Orderer [CRASHED]
             └──► CouchDB (i3-ford)
```

### 2.2 Asynchronous (Kafka) Dependencies

| Producer | Topic | Consumer |
|----------|-------|---------|
| Engage Web | `engage.email-events` | Engage Kafka Consumer |
| Engage Web | `engage.sms-events` | Engage Kafka Consumer |
| Engage Web | `engage.ai-personalize` | Engage Kafka Consumer |
| Campaign Agent | `engage.campaign-trigger` | Engage Kafka Consumer |
| Engage Consumer | `engage.ai-personalize.dlq` | Dead-letter queue (no consumer) |
| EvalOS Web | `evalos-submissions` | **No consumer confirmed** |
| FORD API | `admissions-leads` | Admissions Agent |
| AI Lab | `ai-lab-usage` | **No consumer confirmed** |
| OTT | `ott-stream-events` | **No consumer confirmed** |

### 2.3 Storage Dependencies

| Service | Store | Type | Isolation |
|---------|-------|------|-----------|
| All SQL services | PostgreSQL (Crunchy) | i3-data | Per-schema + RLS |
| Admissions | ChromaDB | i3-admissions | Collection-per-tenant (unconfirmed) |
| AI Lab | ChromaDB | i3-ai-lab | Collection-per-tenant (unconfirmed) |
| Onboarding Agent | Redis | i3-data | TTL-keyed plan store |
| LiteLLM | PostgreSQL | i3-data | Shared |
| Langfuse | PostgreSQL | i3-data | Project-scoped |
| FORD | CouchDB | i3-ford | Per-peer world state |

---

## 3. Data-Flow Map

### 3.1 Admissions RAG Flow
```
User Query
  → Kong (JWT verify → Keycloak)
  → Admissions Agent /chat
      → Lobster Trap firewall (14 regex patterns)
      → ChromaDB similarity search
      → LiteLLM /v1/chat/completions (granite-nano / qwen-fast)
          → Ollama (local model)
          → Langfuse trace (with tenant_id metadata)
      → Response (+ context chunks)
```

### 3.2 Campaign Send Flow
```
PMaaS Web /api/campaigns/send (HTTP 200 — SYNC, not async)
  → Campaign Agent (Python)
      → LiteLLM (personalisation)
      → Kafka engage.campaign-trigger
          → Engage Consumer
              → Brevo API (email/SMS)
```
**Gap**: Campaign send is synchronous (returns HTTP 200). P3-GATE-03 requires HTTP 202.

### 3.3 Evaluation Flow
```
Candidate → EvalOS Web /api/exam/[examId]/submit
  → PostgreSQL (attempt record)
  → LiteLLM (AI grading — synchronous)
  → Certificate generation
```

### 3.4 FORD USSD Flow (Planned — not live)
```
Safaricom USSD → AT API → FORD API /ussd
  → HMAC(NID) token
  → Hyperledger Fabric orderer [CRASHED]
  → ballotPrivate collection (private data — HC-8)
```

---

## 4. Security Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| SEC-01 | 🔴 CRITICAL | Brevo API key exposed in HTML docs (3 files) | ✅ Redacted + key must be rotated |
| SEC-02 | 🔴 CRITICAL | HC-7 VIOLATION: `DEV_BYPASS_AUTH` guard present in `onboarding-agent/src/security/keycloak-auth.ts:51–53` | ⚠️ Must be removed before Phase 2 |
| SEC-03 | 🔴 CRITICAL | `VOICE_API_KEY` hardcoded literal in `platform/voice/voice-deploy.yaml:63` | ⬜ Must be scrubbed |
| SEC-04 | 🔴 HIGH | 7 `REPLACE_FROM_VAULT` placeholders in `admissions-secrets` | ⬜ Must be populated |
| SEC-05 | 🟡 MEDIUM | OpenBao initialized but root token not persisted — application secrets in K8s Secrets, not OpenBao KV | ⬜ Phase 2: migrate to OpenBao KV |
| SEC-06 | 🟡 MEDIUM | admissions-agent `KEYCLOAK_ISSUER` was internal URL — fixed via `oc set env` but not in YAML manifest | ⬜ Fix YAML in deploy |
| SEC-07 | 🟡 MEDIUM | Engage `subject_id_hash` falls back to raw email (TODO in `campaigns/send/route.ts`) — HC-6 risk | ⬜ Phase 2: enforce HMAC |
| SEC-08 | 🟢 LOW | chromadb==0.5.7 incompatible with llama-index-vector-stores-chroma==0.1.10 — pinned to 0.4.24 in requirements.txt but image not rebuilt | ⬜ Phase 2: image rebuild |
| SEC-09 | 🟢 LOW | Tekton `git-clone` PVC workspace collision — non-blocking | ⬜ Phase 2 cleanup |

---

## 5. Tenant Isolation Findings

| Layer | Status | Detail |
|-------|--------|--------|
| PostgreSQL RLS | ✅ Deployed | 17-table baseline RLS (`V1__baseline_tenant_rls.sql`); `tenant_id UUID NOT NULL` on all tables |
| Kafka events | ⚠️ Partial | `tenant_id` in CloudEvent envelope required by HC-4 — not confirmed in all producers |
| ChromaDB (admissions) | ⚠️ Unconfirmed | Collection-per-tenant not verified — single collection may serve all tenants |
| ChromaDB (AI Lab) | ⚠️ Unconfirmed | Same as above |
| LiteLLM/Langfuse | ✅ Confirmed | `metadata.tenant_id` forwarded on all completions — P1-GATE-07 evidence |
| JWT claims | ⚠️ Partial | `tenant_id` claim absent from `i3-ragas-sa` service account token; falls back to `FALLBACK_TENANT_ID` |
| Onboarding Agent | ⚠️ Partial | Redis plan store is TTL-keyed but not tenant-partitioned |
| AfroERP | ❓ Unknown | Frappe multi-tenancy model not confirmed |
| EvalOS base tables | ⚠️ Partial | `tenant_id` on some tables not confirmed (partial HC-4 compliance) |

---

## 6. Agent Safety Findings

| Agent | Autonomy Level | Lobster Trap | Tool Auth Gate | Finding |
|-------|---------------|-------------|---------------|---------|
| Admissions Agent | L1 | ✅ 14-pattern firewall | ✅ MCP Gateway | HC-3 compliant |
| Campaign Agent | L1 | ⚠️ Not confirmed | ⚠️ Direct Kafka | No prompt firewall found |
| Onboarding Agent | L0/L1 | ✅ lobster-trap.ts | ✅ via planner | HC-3 compliant |
| EvalOS Zuri | L1 | ⚠️ Not confirmed | ⚠️ Direct LiteLLM | No firewall confirmed |
| PMaaS Agent | L1 | ⚠️ Not confirmed | ⚠️ Direct LiteLLM | No firewall confirmed |

**HC-3 Gap**: Campaign Agent, EvalOS Zuri, and PMaaS Agent call LiteLLM directly without a Lobster Trap firewall or MCP gateway authorization layer.

---

## 7. Model Gateway Findings

### 7.1 Available Models (LiteLLM OSS config)

| Alias | Backend | Type | Status |
|-------|---------|------|--------|
| `granite-nano` | Ollama | Chat (135M) | ✅ Running |
| `embed` | Ollama `nomic-embed-text:v1.5` | Embedding | ✅ Pulled (was missing) |
| `qwen-fast` | Ollama | Chat (7B) | ✅ Running |
| `coder` | Ollama | Code (7B) | ✅ Running |
| `qwen-heavy` | Ollama | Chat (72B) | ✅ Running |
| `vision` | Ollama | Vision | ✅ Running |
| `watsonx/ibm/granite-3-8b-instruct` | IBM watsonx.ai | Chat | ⚠️ Key = REMOVED |
| `watsonx/ibm/slate-125m-english-rtrvr` | IBM watsonx.ai | Embedding | ⚠️ Key = REMOVED |

### 7.2 Findings
- WatsonX API key scrubbed (`REMOVED`) — watsonx models not available until key re-provisioned
- `embed` model (`nomic-embed-text:v1.5`) was missing from Ollama — pulled during P1 gate work
- No model fallback chain for `granite-nano` (only qwen-fast/heavy have fallbacks)
- Langfuse integration confirmed at `langfuse_host: http://langfuse.i3-model-gateway.svc.cluster.local:3000`
- RAGAS quality: faithfulness=0.975, context_precision=0.800 (qwen-fast judge, 10 queries)

---

## 8. Event Catalogue

| Topic | CloudEvent Type | Producer | Consumer | HC-4 `tenant_id` |
|-------|----------------|----------|---------|-----------------|
| `engage.email-events` | `com.i3.engage.email.send` | Engage Web | Engage Consumer | ⚠️ Not confirmed |
| `engage.sms-events` | `com.i3.engage.sms.send` | Engage Web | Engage Consumer | ⚠️ Not confirmed |
| `engage.ai-personalize` | `com.i3.engage.ai.personalize` | Engage Web | Engage Consumer | ⚠️ Not confirmed |
| `engage.campaign-trigger` | `com.i3.engage.campaign.trigger` | Campaign Agent | Engage Consumer | ⚠️ Not confirmed |
| `engage.ai-personalize.dlq` | DLQ | Engage Consumer | **None** | N/A |
| `admissions-leads` | `com.i3.admissions.lead` | FORD API | Admissions Agent | ⚠️ Not confirmed |
| `evalos-submissions` | `com.i3.evalos.submission` | EvalOS Web | **None confirmed** | N/A |
| `ai-lab-usage` | `com.i3.ailab.usage` | AI Lab | **None confirmed** | N/A |
| `ott-stream-events` | `com.i3.ott.stream` | OTT | **None confirmed** | N/A |

**Gap**: 5 of 9 topics have no confirmed consumer. 0 of 9 topics have confirmed HC-4 `tenant_id` in CloudEvent envelope.

---

## 9. Infrastructure Findings

| Component | Finding | Severity |
|-----------|---------|----------|
| Fabric Orderer `orderer-0` | CrashLoopBackOff — MSP crypto never enrolled | 🔴 Phase 3 blocker |
| OpenBao | Initialized + unsealed but root token not persisted; apps use K8s Secrets directly | 🟡 Phase 2 |
| Peer `peer0-i3tech` | FailedCreate — hostPath volume forbidden by SCC | 🔴 Phase 3 blocker |
| Tekton git-clone | PVC workspace collision — pipeline not fully end-to-end | 🟡 Non-blocking |
| KEDA | Configured for model-gateway autoscaling — not verified functional | 🟡 Phase 3 |
| Prometheus | `i3-platform-alerts` PrometheusRule present | ✅ |
| Grafana | StatefulSet 1/1 Ready, PVC Bound | ✅ |
| Redis | Running in i3-data — used by onboarding agent plan store | ✅ |
| PostgreSQL | Crunchy Postgres, 3-node HA, i3-data | ✅ |
| Kafka | KRaft mode, 3 brokers, i3-messaging | ✅ |
| Keycloak | Realm `i3` active; `ford-ca` CA running; `i3-ragas-sa` service account created | ✅ |

---

## 10. Test Inventory

| Test File | Gate | Result | Notes |
|-----------|------|--------|-------|
| `platform/ford/tests/test_otp_ratelimit.py` | P1-GATE-08 | ✅ 14/14 PASS | HC-6 HMAC-keyed rate limit |
| `onboarding-agent/src/__tests__/skills-assessor.test.ts` | P1-GATE-09 | ✅ 9/9 PASS | Subagent isolation |
| `platform/testing/ragas_score.py` | P1-GATE-10 | ✅ PASS | faithfulness=0.975, cp=0.800 |
| `platform/testing/ragas/test_ragas_thresholds.py` | P3-GATE-12 | ⬜ Not run | Full 4-metric suite |
| `platform/testing/locust/locustfile.py` | P3-GATE-13 | ⬜ Not run | p95 latency baseline |
| `platform/testing/promptfoo-config.yaml` | P3-GATE-10 | ⬜ Not run | Red-team evaluation |
| Go chaincode unit tests | P3-GATE-05 | ⬜ Not written | HC-8 ballot secrecy |
| Consent service tests | P2-GATE-01 | ⬜ Not written | Circuit-breaker |
| Agent registry tests | P2-GATE-02 | ⬜ Not written | 6-manifest response |
| MCP gateway tests | P2-GATE-03 | ⬜ Not written | Forbidden tool → 403 |

---

## 11. Unknowns

| # | Unknown | Risk | Resolution |
|---|---------|------|-----------|
| U-01 | SmartLab service — tenant_id schema, auth, Kafka usage, tests all unconfirmed | Medium | Audit in Phase 2 |
| U-02 | AfroERP multi-tenancy model (Frappe SaaS vs single-tenant) | High | Architecture review Phase 2 |
| U-03 | ChromaDB per-tenant collection isolation in admissions + AI Lab | High | Verify + enforce Phase 2 |
| U-04 | WatsonX API key removed — watsonx models unavailable | Medium | Re-provision in Phase 2 |
| U-05 | Onboarding Agent namespace `i3-onboarding` not in `namespaces.yaml` | Low | Add to namespace manifest |
| U-06 | EvalOS `evalos-submissions` Kafka topic has no consumer | Medium | Implement or remove Phase 2 |
| U-07 | Consent service — code exists, not deployed, not tested | Critical | Phase 2 P2-GATE-01 |
| U-08 | All 9 Kafka topics lack confirmed HC-4 `tenant_id` in CloudEvent envelope | High | Phase 2 event schema audit |
| U-09 | Campaign Agent, EvalOS Zuri, PMaaS Agent have no Lobster Trap firewall | High | Phase 2 HC-3 compliance |
| U-10 | `peer0-i3tech` pod FailedCreate (hostPath SCC violation) | High | Phase 3 SCC fix |
| U-11 | Fabric MSP crypto material never generated for orderer or peers | Critical | Phase 3 `fabric-ca-client enroll` |

---

## 12. Risk Register

| Risk ID | Description | Likelihood | Impact | Mitigation |
|---------|-------------|-----------|--------|-----------|
| R-01 | HC-7 `DEV_BYPASS_AUTH` guard in onboarding-agent reaches production | Medium | Critical | Remove before Phase 2 merge — **blocking** |
| R-02 | Brevo API key was in git (caught by GH push protection) | Confirmed | High | Key rotated; `.gitleaks.toml` updated with Brevo rule |
| R-03 | Fabric IEBC deadline (16 Mar 2027) missed if MSP enrollment not started by Nov 2026 | Medium | Critical | HC-2 — begin chaincode scaffold in Phase 3 immediately |
| R-04 | ChromaDB single collection serving all tenants — data leakage between tenants | Medium | Critical | Verify + enforce collection-per-tenant Phase 2 |
| R-05 | 5 Kafka topics with no consumer → silent data loss | High | High | Implement consumers or remove topics Phase 2 |
| R-06 | OpenBao not used for secret injection — K8s Secrets as fallback | High | Medium | Migrate to OpenBao KV Phase 2 per HC-6 |
| R-07 | WatsonX key removed — if Ollama goes down, no LLM fallback | Medium | High | Re-provision watsonx key Phase 2 |
| R-08 | admissions-agent chromadb/llama-index version mismatch → all /chat 500 errors | Confirmed | High | Rebuild image with chromadb==0.4.24 Phase 2 |
| R-09 | `REPLACE_FROM_VAULT` placeholders in admissions-secrets — 7 env vars missing | Confirmed | Medium | Populate from OpenBao before Phase 2 deploy |
| R-10 | AfroERP Frappe tenancy model unknown — may not support HC-4 `tenant_id` | Low | High | Architecture review Phase 2 |

---

## 13. Recommended Implementation Sequence (Phase 2)

Priority ordered by dependency and risk:

### Track A — Security & Compliance (unblock P2 entry)
1. **A-1** Remove `DEV_BYPASS_AUTH` guard from `onboarding-agent/src/security/keycloak-auth.ts` (R-01, HC-7) — **BLOCKING**
2. **A-2** Rotate Brevo API key in Brevo dashboard; update `engage-secrets` + `pmaas-secrets` on cluster (SEC-01)
3. **A-3** Scrub `VOICE_API_KEY` hardcoded literal from `voice-deploy.yaml` (SEC-03)
4. **A-4** Populate 7 `REPLACE_FROM_VAULT` entries in `admissions-secrets` via OpenBao (SEC-04, R-09)
5. **A-5** Fix `KEYCLOAK_ISSUER` in `admissions-deploy.yaml` YAML manifest (matches `oc set env` already applied)

### Track B — Consent Service (P2-GATE-01)
6. **B-1** Deploy consent service to `i3-consent` namespace
7. **B-2** Implement circuit-breaker fail-closed in admissions, campaign, and FORD agents
8. **B-3** Write consent service tests (P2-GATE-01 sensor)

### Track C — Agent Registry + MCP (P2-GATE-02/03)
9. **C-1** Register all 6 agent manifests in Agent Registry (admissions, campaign, onboarding, evalos, pmaas, ford)
10. **C-2** Add decision log emission to all agents
11. **C-3** Verify MCP gateway returns 403 on forbidden tool calls (P2-GATE-03)

### Track D — Tenant Isolation Hardening (P2-GATE-04)
12. **D-1** Audit + enforce ChromaDB collection-per-tenant (admissions + AI Lab) (U-03, R-04)
13. **D-2** Add `tenant_id` to all 9 Kafka CloudEvent envelopes (HC-4, U-08)
14. **D-3** Fix Engage `subject_id_hash` fallback to enforce HMAC (SEC-07)
15. **D-4** Add `tenant_id` JWT claim to Keycloak client mappers for service accounts

### Track E — Agent Safety (HC-3)
16. **E-1** Add Lobster Trap firewall to Campaign Agent (U-09)
17. **E-2** Add Lobster Trap firewall to EvalOS Zuri agent (U-09)
18. **E-3** Add Lobster Trap firewall to PMaaS Agent (U-09)
19. **E-4** Route all agent LLM calls through MCP Gateway (HC-5)

### Track F — Image + Code Fixes
20. **F-1** Rebuild admissions-agent image with `chromadb==0.4.24` (R-08, SEC-08)
21. **F-2** Add `i3-onboarding` to `namespaces.yaml` (U-05)
22. **F-3** Re-provision WatsonX API key in LiteLLM config (U-04, R-07)
23. **F-4** Fix Tekton git-clone PVC workspace collision (SEC-09)

### Track G — Phase 3 Pre-work (start in parallel)
24. **G-1** Run `fabric-ca-client enroll` for orderer MSP (R-03, U-11)
25. **G-2** Fix `peer0-i3tech` SCC hostPath violation (U-10)
26. **G-3** Scaffold Hyperledger Fabric chaincode (HC-2, HC-8)

---

## 14. P1 Gate Evidence Summary

All 12 P1 exit gates passed. Evidence files in `platform/testing/`:

| Gate | Evidence File | Score |
|------|--------------|-------|
| P1-GATE-07 | `langfuse-gate-evidence.json` | PASS |
| P1-GATE-10 | `ragas-gate-evidence.json` | faithfulness=0.975 |
| All 12 | `p1-gate-evidence.json` | 12/12 PASS |

---

## 15. EXPLORE Phase Decision

**EXPLORE STATUS: READY-WITH-CONDITIONS**

### Conditions that must be resolved before first Plan task is merged to `main`:
1. **HC-7 blocker**: Remove `DEV_BYPASS_AUTH` guard from `keycloak-auth.ts` (A-1 above)
2. **Brevo key rotation**: Rotate the exposed API key in Brevo dashboard (A-2 above)

All other findings are tracked in the risk register and implementation sequence above.
Plan may proceed. Phase 2 entry is approved subject to the two conditions above being
resolved within the first Plan sprint.

---
*Generated by Bob (IBM Bob AI software engineer) | i3 AI Platform | 2026-09-22*
