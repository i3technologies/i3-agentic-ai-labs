# i3 Technologies — Unified Technical Implementation Guide for IBM Bob
## Consolidated Architecture, Engineering Standards & Master Prompt Catalog
### Explore → Plan → Implement → Verify

**Prepared for:** Philip Mukiti, CEO & Solutions Architect, i3 Technologies (Instrumented Interconnected & Intelligent Technologies Limited)
**Document type:** Master engineering execution guide and IBM Bob prompt catalog
**Consolidates:**
1. *i3 Modernisation Technical Implementation Blueprint*, v1.0, Sept 2026
2. *IBM Bob Modernisation Playbook & Prompt Catalog*, Sept 2026
3. *i3 IBM Bob 4-Phase Development Playbook*
4. *i3 IBM Bob Modernisation Operational Playbook*

**Purpose of this document:** the four source documents above overlap heavily and were produced at different times with different levels of detail. This guide merges them into a single non-redundant operating contract — the version to actually upload into IBM Bob's context window — plus a section of current (2026) agentic-engineering innovations that should be layered on top of what the source documents already specify.

**Working principle:** IBM Bob is a controlled engineering partner, not an autonomous architect. It executes inside the constraints below. It does not replace architecture governance, security sign-off, product ownership, or human approval for consequential actions.

---

## Table of Contents

1. How to Use This Document With Bob
2. Architecture Ground Truth (What Exists, What's Aspirational, What's Being Rebuilt)
3. Non-Negotiable Hard Constraints (HC-1 → HC-8)
4. Engineering Principles (P1 → P10)
5. Bob Workspace / Repository Control Plane
6. Agent & Tool Risk-Tier Model
7. Current Innovations & Best-Practice Patterns to Apply
8. The Four-Phase Development Cycle
   - Phase 1 — Explore (prompts + exit gate)
   - Phase 2 — Plan (prompts + exit gate)
   - Phase 3 — Implement (prompts + discipline checklist)
   - Phase 4 — Verify (prompts + production readiness scorecard)
9. Master System Prompt for IBM Bob
10. Recommended First 10 Bob Sessions (Quick Start)
11. Definition of Done
12. Capability Claim Matrix (what may be said, and only when)
13. Strategic End-State Architecture
14. Immediate Execution Checklist

---

# 1. How to Use This Document With Bob

1. **Upload this file first**, then the *Modernisation Technical Implementation Blueprint*, into every new Bob task that touches this programme. Bob performs best with explicit constraints and acceptance criteria repeated in-context, not assumed from a prior session.
2. **One phase gate at a time.** Bob must not move from Explore → Plan → Implement → Verify until the human Tech Lead has signed off the exit gate for the current phase.
3. **Open a new Bob task for every prompt below.** Long-running tasks accumulate stale context; a fresh task per prompt keeps Bob's context window lean and its answers grounded in what it actually inspected this session.
4. **Never let Bob contradict a hard constraint (§3) or an architecture rule (§2.3),** regardless of how a task is framed. Repeat the relevant constraint IDs inline in every prompt you send.
5. **GAP discipline.** Anything not yet verified (GPU inference, Nairobi residency, per-tenant metering, WORM audit, multi-tenancy enforcement) must be tagged `// [GAP] Workstream <id> — not yet shippable` in code, docs and demos. It may never be described in the present tense in customer-facing material until its acceptance evidence exists (see §12).
6. **Risk-tiered autonomy governs Bob's own output**, not just the agents it builds. Map every task to the tier model in §6 before deciding how much of its output merges without review.

---

# 2. Architecture Ground Truth

## 2.1 Strategic decision: one core, not five platforms

The rebuild is **not** a green-field rewrite of every product. It is: **rebuild the shared core once; keep and extend the production assets that already work.**

**Rebuilt once, shared by everything:**
- One identity plane — single Keycloak realm (`i3`), SSO for every client app, present and future
- One model & agent gateway — LiteLLM + a new Agentic Orchestration & MCP Gateway; no application talks to a model, or to another application's data, directly
- One metering/billing spine — per-project API keys → Postgres `spend_logs` → nightly ETL → per-customer statements
- One governance/audit layer — WORM audit store, PII pre-filter, evaluation harness, agent risk-tiering
- One event backbone — Kafka, nine-field CloudEvent envelope

**Kept and extended, not rebuilt:**
- **EvalOS** (exam engine, Study Coach, Coding Lab, AI Interview) — already ahead of benchmark on AI-assisted assessment
- **AfroERP** and **Engage** — production financial (M-Pesa Daraja, KRA eTIMS) and messaging (WhatsApp/SMS) rails; these become **tool endpoints** for the agent mesh, not services to re-platform
- **Directus CMS** — extended for OTT/authoring metadata rather than standing up a second CMS
- The existing production OpenShift namespaces and the multi-account IBM Cloud fabric (Production / SmartLabs Compute / Model Gateway+GPU) — kept as the infrastructure floor

## 2.2 Current-state truth Bob must treat as authoritative until re-verified

| Area | Verified current state | Gap workstream |
|---|---|---|
| Compute region | ROKS footprint is Frankfurt | **B3** — Nairobi residency is a future workstream, not present-tense fact |
| GPU | Worker nodes are CPU-based | **B1** — GPU acceleration is a future workstream |
| Model gateway keys | LiteLLM/Ollama exists but a **shared master key** is still in circulation | **B2** — must be eliminated for normal client operation |
| Metering | Not yet implemented per-tenant | **B2** |
| Multi-tenancy | Represented in design, not yet enforced technically | **B4** |
| Audit | WORM audit storage is a required implementation, not yet live | **B4** |

**Operating principle:** *code evidence beats documentation; runtime evidence beats assumptions; automated acceptance tests beat claims.*

## 2.3 Architecture rules (repeat verbatim in every relevant prompt)

| # | Rule | Enforcement |
|---|---|---|
| R1 | All model calls go through LiteLLM. No direct Ollama/vLLM calls from any client. | Code review + network policy |
| R2 | All inter-service tool calls go through the MCP Tool Gateway. Agents never hold direct DB credentials. | OpenBao/Vault-injected credentials only |
| R3 | One Keycloak realm (`i3`). One SSO group claim drives RBAC in every app. | Shared realm config + CI check |
| R4 | Per-project LiteLLM API keys only. The master key is disabled for interactive use, kept only as a break-glass Vault-managed service account. | LiteLLM config + nightly audit job |
| R5 | Metering/billing reads only from the Postgres spend ledger (`spend_logs`). No product invoices independently. | Single ETL pipeline |

**Architecture invariant:** client applications must never bypass the shared identity, model/agent, governance or metering layers — regardless of how convenient a direct call looks in a given sprint.

---

# 3. Non-Negotiable Hard Constraints (HC-1 → HC-8)

Install these as repository rules (`.bob/rules/01-hard-constraints.md`, §5) before any implementation task.

| ID | Constraint | Enforcement rule |
|---|---|---|
| **HC-1** | **Namespace isolation.** Never modify, query, deploy to, or generate manifests for `solution-01` … `solution-08`. | If a task appears to require touching one of these, stop and report the dependency instead of proceeding. |
| **HC-2** | **Statutory clock.** Hyperledger Fabric 2.5 chaincode and the USSD gateway bridge must reach staging verification by **November 2026**, supporting the **16 March 2027 IEBC** deadline. | Treat as a programme constraint, never as permission to skip security or verification. |
| **HC-3** | **Agent autonomy ceiling.** All new AI agents ship at **L0 — Observe/Read** or **L1 — Supervised Draft/Propose**. No L2/L3 without documented evaluation evidence and explicit human approval. | Registry-enforced at the MCP Gateway. |
| **HC-4** | **Tenant isolation.** `tenant_id UUID NOT NULL` enforced across PostgreSQL tables, RLS policies, application queries, event envelopes, caches, audit records, background jobs, and API authorization context. | A missing tenant boundary is a release blocker. |
| **HC-5** | **Agentic safety triangle.** A generative model must never directly execute a state-mutating tool. All consequential actions pass: `Agent → Orchestrator → MCP Gateway → Deterministic Policy/Risk Check → Human Approval (where required) → Tool → Audit Event`. | MCP Gateway interceptor on every tool call. |
| **HC-6** | **Identifier anonymisation.** Kenyan National IDs and phone numbers must use **keyed HMAC-SHA256** with `MEMBER_HMAC_SECRET` stored in OpenBao — never raw SHA-256. | Secret sweep / static analysis. |
| **HC-7** | **No auth bypass.** `DEV_BYPASS_AUTH=true` must never appear in tracked or non-development configuration. | Presence in a protected environment is a release blocker. |
| **HC-8** | **Ballot secrecy.** Member identity verification and ballot choices remain architecturally separated — use Fabric Private Data Collections or an equivalent cryptographically separated design. | Architecture review + red-team. |

---

# 4. Engineering Principles (P1 → P10)

| # | Principle | What it means in practice |
|---|---|---|
| **P1** | Small bounded changes | One feature, migration, or remediation per task. Never "modernise the whole platform" in one shot. |
| **P2** | Inspect before editing | Bob must first map files, call graph, data/config/API dependencies, DB tables, event flows, deployment resources, and tests. |
| **P3** | No speculative rewrites | Don't replace working infrastructure because a technology is fashionable. |
| **P4** | Contract-first | Before implementation: API, event contract, data model, authorization, tenancy, error model, observability, acceptance tests. |
| **P5** | Secure by default | Security is part of implementation, not a later phase. |
| **P6** | Observable by default | Every production component ships with structured logs, metrics, trace/correlation ID, health + readiness endpoints, audit events. |
| **P7** | Idempotent operations | Every external event handler and state-changing operation defines its idempotency behaviour. |
| **P8** | Human approval for consequential actions | Financial, credentialing, partner-attribution, ballot, security, and customer-impacting operations require appropriate approval gates. |
| **P9** | Reversible deployment | Every migration has a rollback path, a compatibility strategy, backup/recovery, and a feature flag where appropriate. |
| **P10** | Evidence-based completion | A task is done when acceptance evidence passes — not when code was generated. |

---

# 5. Bob Workspace / Repository Control Plane

Install these files before broad implementation begins.

```text
.bob/
├── rules/
│   ├── 01-hard-constraints.md        (HC-1 → HC-8, verbatim from §3)
│   ├── 02-architecture-standards.md  (polyglot engineering standards, below)
│   ├── 03-security-standards.md
│   ├── 04-testing-standards.md
│   └── 05-definition-of-done.md      (§11)
├── custom_modes.yaml
└── mcp.json

platform/
├── docs/{adr,architecture,api,events,runbooks}/
├── schemas/
├── services/
├── agents/
├── mcp/
├── migrations/
├── tests/
├── observability/
└── security/
```

### 5.1 `.bob/rules/02-architecture-standards.md` — polyglot engineering standards

```markdown
## Python (FastAPI & Kafka consumers)
- Connection pooling: use asyncpg.create_pool() inside the FastAPI lifespan.
  NEVER call asyncio.new_event_loop() or asyncpg.connect() inside a message handler.
- All database calls use async context managers: `async with pool.acquire() as conn:`
- Parse every incoming Kafka event through a Pydantic model before use.
- All external user input passes the 12-pattern "Lobster Trap" prompt-injection
  firewall before reaching prompt assembly.

## TypeScript / Node.js (Next.js / Express)
- rejectUnauthorized: true on every DB pool; mount the Crunchy Postgres CA cert.
- Session/plan state lives in Redis with strict TTLs — never an in-memory Map
  (breaks horizontal scaling and HPA).
- Parallel agent/subagent calls use Promise.allSettled to avoid cascading timeouts.
- Webhook signatures (X-Hub-Signature-256, etc.) are verified with
  crypto.timingSafeEqual — never a plain string comparison.
```

### 5.2 Custom Bob modes

| Mode | Purpose |
|---|---|
| `🔍 i3-audit` | Read-only exploration, dependency mapping, secret sweeps |
| `🧠 i3-mesh-architect` | ADRs, service/DB/event contracts, agent-mesh design |
| `🛡️ i3-remediation` | Security fixes, credential rotation, hardening |
| `⚡ i3-runtime-opt` | Performance, CI/CD, connection-pool and event-loop fixes |
| `⛓️ i3-fabric-blockchain` | Hyperledger Fabric chaincode + USSD bridge work |
| `🔍 i3-independent-verifier` *(add this one)* | Read-only verification of implementation, security, tenancy, tests, deployment manifests and evidence — **not the same agent that wrote the code being verified** |

### 5.3 MCP guard tools (`.bob/mcp.json`)

Expose at minimum:

- `audit_sql_ast` — validates every `CREATE TABLE` against tenancy/RLS/index rules before it ships
- `validate_agent_manifest` — checks a proposed agent registry entry against HC-3/HC-5
- `verify_cloudevent_envelope` — checks an event payload against the nine-field schema (below)
- `test_prompt_injection` — runs the Lobster Trap suite against a prompt-assembly path

---

# 6. Agent & Tool Risk-Tier Model

This tier model governs **both** the AI agents i3 builds and Bob's own autonomy on a given task.

| Tier | Scope | Examples | Autonomy |
|---|---|---|---|
| **0 — Read** | Read-only queries | Docs, dashboards, log queries | Full auto |
| **1 — Low-risk** | Non-prod writes | Test fixtures, dev-namespace changes | Full auto + CI |
| **2 — Customer-facing** | Prod writes visible to users | Content publish, enrolments, grading | Human review before merge |
| **3 — Business-impacting** | Money, contracts, partner actions | Credit notes, partner matching, billing, PR creation (e.g. a code-writing agent opening its own pull requests) | Human approval **default** |
| **4 — High-risk** | Irreversible or regulated | Deletes, PII exports, model promotion, ballot-adjacent operations | Recommendation-only; a human executes |

Every MCP tool additionally carries: `risk_tier (0-4)`, `side_effect_class (read | reversible_write | business_write | irreversible)`, `required_roles`, `tenant_scope`, `approval_required`, `idempotency_requirement`.

---

# 7. Current Innovations & Best-Practice Patterns to Apply

These are the specific, currently-relevant engineering patterns worth deliberately building into this programme — some already named in the source blueprint, some standard current (2026) practice for agentic platforms generally. Bob should treat this table as a checklist when designing any new service, agent, or pipeline.

| Innovation | What it buys you | Where it applies here |
|---|---|---|
| **Agents propose, policy disposes** (deterministic gate between model and tool execution) | Removes the model itself as a single point of failure for anything consequential | Core MCP Gateway pattern (HC-5) — the architectural difference between a chatbot and a governed agent platform |
| **Per-key/per-project budget guardrails with fail-closed rejection** | Predictable AI spend; a real commercial claim to make to finance-sensitive customers (banks, universities) | LiteLLM key hierarchy (B2); over-quota calls are rejected with a tenant-facing error, not silently throttled |
| **GPU pool with automatic CPU fallback** | A GPU node failure degrades latency, never availability — appliance-grade resilience, not a demo-only GPU claim | B1 routing config; the same pattern later powers the Nexus Appliance / Afriq Box |
| **Bantu-aware BPE tokenizer for Swahili/Sheng** | Materially lower per-token cost and better multilingual quality than reusing a generic Llama/Qwen tokenizer unmodified | AfriqAI; must be validated (not assumed) against real Swahili/Sheng corpora before pricing is built on it |
| **Namespace-per-tenant Helm template** (`i3-tenant`) | A university, bank, or partner sandbox is provisioned in minutes with identity, quotas, network policy and a scoped LiteLLM key baked in — this *is* the EduBridge/E³ sales demo | B4; parameterised by tenant tier (sandbox/standard/dedicated) |
| **WORM (write-once-read-many) audit pipeline with retention lock** | Tamper-evident proof of "who did what, when, to which tenant" — the artefact that actually earns an "audit-ready" claim | B4; append-only object storage + an auditor query CLI |
| **Keyed HMAC-SHA256 for all sensitive identifiers** | Defensible anonymisation instead of trivially-reversible raw hashing | HC-6; applied to National IDs, phone numbers, M-Pesa transaction IDs |
| **Semantic response caching at the model gateway** (similarity threshold, e.g. ≥0.95) | Cuts model-call cost and latency for near-duplicate prompts without a bespoke cache per product | LiteLLM + Redis; shared across every consuming product |
| **Event-driven consumers with dead-letter queues (KEDA-scaled)** | Consumers scale to load and unprocessable events don't silently vanish or crash the worker | Kafka consumer layer across Engage/PMaaS/AfroERP integrations |
| **Multi-gate CI pipeline** (secret scan → container/dependency scan → RAG/answer-quality eval → adversarial prompt eval) | Security and AI-quality regressions are caught before merge, not in production | Tekton (or equivalent) pipeline gating every PR that touches a model-facing or secret-handling path |
| **Prompt-injection firewall applied uniformly** (a fixed set of detection patterns run on every external input before prompt assembly) | One implementation instead of five bespoke, inconsistent filters per agent | Applied to every agent in the registry, not just customer-facing ones |
| **Offline-first PWA writes with background sync** | Field agents and low-connectivity users (a real constraint across East Africa) don't lose work to a dropped connection | Client apps built on Next.js; a local write queue reconciles once connectivity returns |
| **NER-based PII pre-filter as a logging sidecar** | Sensitive data never reaches logs/traces in the first place, instead of being redacted after the fact | Applied ahead of any log/trace write across the platform, reused by AfriqAI, EduBridge, i3 E³ |
| **One shared ReAct planner (Reason → Act → Observe → Confirm)** across every agent | One implementation to secure, evaluate and improve instead of five divergent ones | Shared by Sage, Mfumo++, Nuru++, and every i3 E³ ecosystem agent |
| **Agent Registry + risk-tier enforcement at the gateway, not in application code** | Autonomy ceilings and approval requirements are enforced centrally and can't be silently bypassed by a new product team | One registry consumed by every agent-hosting product |
| **Model cards + release gate tied to an evaluation harness** | No model or quantisation change ships without a green suite and a one-page card describing what it was actually tested on | B5; includes a dedicated Swahili/Sheng task suite, not just an English benchmark |
| **W3C Verifiable Credentials for identity/trust artefacts** (partner passports, engineer certifications) | Portable, publicly verifiable credentials instead of a proprietary "trust us" badge | i3 E³ Partner Passport |
| **Contract-first, evidence-based completion (ADR → schema/API/event contract → implementation → acceptance test)** | Prevents "looks done" from being confused with "is done" — the single most important discipline for working safely with an AI coding partner | Applied to every Plan-phase output before Implement begins |
| **Independent verification role, separate from the implementing agent** | The same agent that wrote the code should not be the sole judge of whether it's correct | `i3-independent-verifier` mode (§5.2); mirrors the general principle that AI-assisted code review needs a distinct reviewing context from the authoring context |
| **Machine-verifiable sensor checks over subjective scoring** | "PASS/FAIL with evidence" beats a confidence score or a narrative claim of readiness | Production Readiness Scorecard (§8, Verify phase) |

---

# 8. The Four-Phase Development Cycle

## PHASE 1 — EXPLORE *(read-only)*

**Objective:** build a trustworthy engineering map before touching code. Bob's role: discovery analyst / gap-detection engine.

### EXP-00 — Bob bootstrap / workspace orientation

```text
Act as the Principal Solutions Architect and Engineering Partner for the i3
Technologies Unified Agentic AI Platform. You have been given this
Implementation Guide and the Modernisation Technical Implementation Blueprint.

Before touching any source file, perform a READ-ONLY workspace orientation.

Identify:
1. Repository root and major applications/services.
2. Deployment manifests, Helm charts, Kustomize resources, OpenShift resources.
3. PostgreSQL schemas/migrations.
4. Kafka producers/consumers and event schemas.
5. Redis usage.
6. Keycloak integration.
7. LiteLLM/Ollama/vLLM integration.
8. MCP tools and agent definitions.
9. Existing test suites and CI/CD pipelines.
10. OpenBao/secret references.
11. EvalOS, AfroERP, Engage, SmartLabs, AI Lab/Sage, EduBridge, OTT, i3 E³ components.
12. Any code that touches solution-01 through solution-08 (HC-1 — flag, do not touch).

Do not modify files.

Create:
- docs/architecture/Bob-Workspace-Inventory.md
- docs/architecture/Current-State-Dependency-Map.md

For every major component record: purpose, language/framework, runtime,
deployment mechanism, database dependencies, external integrations,
authentication mechanism, tenant boundary, event dependencies, AI/model
dependencies, tests, operational owner (if discoverable), risk level.

End with:
A. Components safe to modernise
B. Components that must be preserved
C. Unknowns requiring human clarification
D. Hard-constraint violations discovered
E. Recommended Explore follow-up tasks

Do not infer missing facts. Mark unknown information as UNKNOWN.
```

### EXP-01 — Dependency & blast-radius analysis

```text
Act as a Principal Systems Architect. Perform a READ-ONLY dependency and
blast-radius analysis for: **Consent Service** (`i3-consent` namespace —
FastAPI, not yet deployed; code exists at `platform/consent/`).
Admissions Agent, Campaign Agent, and FORD API are the three known callers.
Circuit-breaker fail-closed behaviour is required (U-07, R-07).

Trace: inbound callers, frontend routes, REST APIs, webhooks, Kafka
producers/consumers, PostgreSQL tables, Redis keys, object storage,
LiteLLM/model calls, MCP tools, external systems, deployment resources, tests.

Check: HC-1 namespace isolation, HC-4 tenant propagation, HC-5 agent safety
boundary, authentication/authorization, correlation IDs, idempotency, retry
behaviour.

Produce:
1. Dependency graph in Mermaid
2. Blast-radius assessment (Low/Medium/High) with justification
3. Data-flow summary
4. Failure modes
5. Backward-compatibility requirements
6. Recommended extraction boundary (if refactoring into a bounded service)
7. Tests required before changing the component

Do not modify files.
```

### EXP-02 — Database and tenant-isolation audit

```text
Act as a Principal PostgreSQL and Multi-Tenancy Architect. Perform a
READ-ONLY audit of the database layer.

For every relevant table identify: primary key, tenant_id, foreign keys,
created_at/updated_at, indexes, RLS policies, whether tenant context is
enforced by application code or database policy.

Search specifically for: missing tenant_id, nullable tenant_id, queries
without tenant predicates, unsafe dynamic SQL, cross-tenant joins, unscoped
Redis keys, unscoped object-storage keys, background jobs that lose tenant
context, migrations that would be unsafe in production.

Produce a tenant-isolation matrix (table × finding × severity × fix).

Do not modify files.
```

### EXP-03 — Security & secret sweep

```text
Act as a Principal DevSecOps Engineer. Perform a complete READ-ONLY security
sweep.

Check for: hardcoded credentials, API keys, database passwords, JWT secrets,
model-provider keys, WhatsApp secrets, M-Pesa credentials, webhook secrets,
private keys, DEV_BYPASS_AUTH=true (HC-7), wildcard CORS, unauthenticated
admin endpoints, exposed debug endpoints, raw National-ID/phone hashing
(HC-6 violation — must be keyed HMAC-SHA256), plaintext OTP storage,
TLS-verification-disabled connections, secrets in Git history (if tooling
allows), insecure container configurations, excessive service-account
permissions.

Produce:
| ID | Severity | File | Line | Finding | Exploitability | Recommended Fix | OpenBao Path |

Do not modify files.
```

### EXP-04 — Agent and MCP safety audit

```text
Act as an independent Agentic AI Security Architect. Audit every agent, MCP
server, tool definition and orchestration workflow.

For each agent identify: purpose, autonomy tier, allowed tools,
read/write capabilities, external side effects, data sensitivity, tenant
context, approval requirement, budget, timeout, retry policy, audit events,
prompt-injection controls.

For every MCP tool classify: risk_tier (0-4), side_effect_class
(read | reversible_write | business_write | irreversible), required_roles,
approval_required, tenant_scope, idempotency requirement.

Flag: direct database access by agents, direct state mutation, missing
policy checks, missing audit events, missing tenant context, excessive
autonomy, unrestricted tools. Explicitly flag any agent with PR-opening or
similar write autonomy — this is Tier 3 minimum.

Do not modify files.
```

### EXP-05 — Model gateway audit

```text
Act as a Principal AI Platform Architect. Audit the current LiteLLM, Ollama
and vLLM architecture.

Determine: model aliases, model routing, CPU/GPU paths, fallback behaviour,
authentication, API-key structure, per-project budgets, token accounting,
request logging, PII handling, prompt/response retention, caching, embedding
models, RAG stores, model evaluation, model release process.

Verify whether EVERY application reaches models only through the approved
model gateway (Rule R1) — flag any direct client-to-model path.

Produce: current model routing diagram, model inventory, gap matrix,
recommended routing policy, cost-control opportunities, evaluation
requirements.

Do not modify files.
```

### EXP-06 — Event backbone audit

```text
Act as a Principal Event-Driven Architect. Audit Kafka usage across the
platform.

For every topic identify: producer, consumer, event type, schema/version,
tenant_id, correlation_id, causation_id, actor, timestamp, idempotency key,
retention, retry/DLQ strategy, ordering requirement, PII classification.

Every event must be compatible with the i3 nine-field event envelope:
event_id, event_type, event_version, tenant_id, correlation_id,
causation_id, actor, timestamp, payload.

Produce an event catalogue and identify schema gaps.

Do not modify files.
```

### PHASE 1 EXIT GATE

Do not enter Plan until Bob produces `EXPLORE-GATE.md` containing: current-state architecture, dependency map, data-flow map, security findings, tenant-isolation findings, agent-safety findings, model-gateway findings, event catalogue, infrastructure findings, test inventory, unknowns, risk register, recommended implementation sequence.

```text
Act as an independent Lead Architect. Review all Explore artefacts produced
in this Bob programme. Do not edit code.

Determine whether there is sufficient engineering evidence to enter PLAN.
Evaluate: architecture understanding, dependency understanding, tenant
isolation, security, agent safety, data model, event model, deployment
model, tests, rollback capability.

Return: EXPLORE STATUS: READY | READY-WITH-CONDITIONS | NOT-READY

If NOT-READY, list exact missing evidence.
If READY, produce the top 20 Plan tasks ordered by dependency and risk.

Do not declare a capability production-ready merely because documentation
exists.
```

---

## PHASE 2 — PLAN

**Objective:** convert Explore findings into implementable, testable engineering contracts. Bob's role: architect/planner — Bob drafts, humans approve every ADR.

### PLN-01 — Architecture Decision Record (MADR)

```text
Act as a Principal Enterprise Architect. Create a production-grade MADR
Architecture Decision Record for: **[One of the following — open a
separate Bob task per ADR]**

Priority order (from EXPLORE-GATE §13):
1. Consent Service deployment + circuit-breaker pattern (B-1/B-2, P2-GATE-01)
2. Agent Registry full manifest seeding — admissions, campaign, onboarding, evalos, pmaas, ford (C-1, P2-GATE-02)
3. ChromaDB per-tenant collection isolation — `i3-admissions` + `i3-ai-lab` (D-1, U-03, R-04)
4. HC-4 CloudEvent `tenant_id` enforcement across all 9 Kafka topics (D-2, U-08)
5. Engage `subject_id_hash` HMAC enforcement (D-3, SEC-07)
6. Lobster Trap firewall for Campaign Agent, EvalOS Zuri, PMaaS Agent (E-1/E-3, U-09)
7. OpenBao KV v2 migration — replace K8s Secrets for all application secrets (SEC-05, R-06)

Ground the decision in actual Explore findings — do not invent context.

Include: Status, Deciders, Context, Problem statement, Decision,
Alternatives, Technical drivers, Security implications, Multi-tenancy
implications, Agent-autonomy implications, Data implications, Event
implications, Operational implications, Performance implications, Cost
implications, Rollback strategy, HC-1 through HC-8 mapping, Compliance/
statutory mapping (Kenya DPA 2019, ODPC, IEBC statutory clock where
relevant), Acceptance criteria.

Save: platform/docs/adr/ADR-[NUMBER]-[slug].md

Do not implement the feature yet.
```

### PLN-02 — Service, database and event contract

```text
Act as a Lead Backend and Database Architect. Design the complete technical
contract for: **[One of the following — open a separate Bob task per
service contract]**

Priority order (from EXPLORE-GATE §13):
1. **Consent Service** — DPA 2019 §25 default-deny endpoint; circuit-breaker
   fail-closed interface consumed by admissions (`platform/admissions/admissions_agent.py`),
   campaign (`platform/pmaas/agents/campaign_agent.py`), FORD API (`platform/ford/api/main.py`)
2. **Engage Kafka Producers** — enforce nine-field CloudEvent envelope with
   `tenant_id UUID NOT NULL` on topics: `engage.email-events`, `engage.sms-events`,
   `engage.ai-personalize`, `engage.campaign-trigger`
3. **EvalOS submission consumer** — topic `evalos-submissions` has no confirmed consumer
   (`platform/engage/consumers/kafka_consumers.py` scope)
4. **Onboarding Agent Redis plan store** — tenant-partition Redis keys
   (`onboarding-agent/src/render/taskSync.ts`, `onboarding-agent/src/orchestrator/planner.ts`)

A. REST API — method, path, authentication, authorization, X-Tenant-Id,
   X-Correlation-Id, idempotency key, request/response/error schemas,
   status codes.

B. PostgreSQL 16 schema — UUIDv7 primary keys, tenant_id UUID NOT NULL,
   timestamps, foreign keys, unique constraints, composite indexes
   (tenant_id, created_at DESC), Row-Level Security:
     ALTER TABLE [table] ENABLE ROW LEVEL SECURITY;
     CREATE POLICY tenant_isolation ON [table]
       USING (tenant_id = current_setting('app.tenant_id')::UUID);
   audit columns, soft-delete strategy where appropriate.

C. Event contracts — the nine-field i3 CloudEvent envelope (§EXP-06).

D. Redis contract if required — key naming, tenant scoping, TTL,
   serialization, invalidation.

E. Object-storage contract if required.

F. Security model. G. Observability plan.

Before finalising, invoke the MCP tool audit_sql_ast on every CREATE TABLE
statement and resolve all findings.

Do not implement application code.
```

### PLN-03 — Agent contract (Agent Registry manifest)

```text
Act as a Principal Agentic AI Architect. Design the Agent Registry manifest
for: **[One of the following — open a separate Bob task per agent manifest]**

All six agents discovered in EXP-04 require registry manifests
(C-1, P2-GATE-02):
1. **Admissions Agent** — L1, MCP Gateway ✅, Lobster Trap 14-pattern ✅
   (`platform/admissions/admissions_agent.py`, namespace `i3-admissions`)
2. **Campaign Agent** — L1, NO Lobster Trap, direct Kafka (U-09 gap to resolve first)
   (`platform/pmaas/agents/campaign_agent.py`, namespace `i3-pmaas`)
3. **Onboarding Agent** — L0/L1, lobster-trap.ts ✅
   (`onboarding-agent/src/server.ts`, namespace `i3-onboarding`)
4. **EvalOS Zuri** — L1, NO Lobster Trap, direct LiteLLM (U-09 gap to resolve first)
   (`platform/evalos/`, namespace `i3-evalos`)
5. **PMaaS Agent** — L1, NO Lobster Trap, direct LiteLLM (U-09 gap to resolve first)
   (`platform/pmaas/agents/campaign_agent.py`, namespace `i3-pmaas`)
6. **FORD API agent** — L1, HMAC HC-6 ✅, HC-8 ✅, orderer CrashLoopBackOff (Phase 3 blocker)
   (`platform/ford/api/main.py`, namespace `i3-ford`)

The agent must ship at L0 or L1 (HC-3).

Define: name, version, purpose, autonomy_tier, risk_tier, side_effect_class,
allowed_tools, denied_tools, required_roles, tenant_scope,
data_classification, cost_budget_tokens, max_runtime, retry policy, human
approval policy, audit events, evaluation suite, prompt-firewall
requirements, model policy, fallback behaviour.

No state-mutating tool may be callable without MCP policy authorization
(HC-5).

Produce: 1) YAML manifest 2) evaluation specification 3) threat model
4) approval matrix 5) rollback plan.

Do not implement runtime code.
```

### PLN-04 — MCP tool contract

```text
Act as a Principal MCP Platform Architect. Design an MCP tool for one of
the following (open a separate Bob task per tool):

Priority order (from EXPLORE-GATE §6 agent safety gaps):
1. **`lobster_trap_check`** — wrap the 14-pattern firewall; risk_tier=0,
   side_effect_class=read; required by Campaign Agent, EvalOS Zuri, PMaaS Agent
   before they can be registered (U-09)
2. **`consent_gate_check`** — query Consent Service default-deny;
   risk_tier=1, side_effect_class=read; required by all three callers (U-07)
3. **`chromadb_tenant_search`** — scoped collection-per-tenant vector search;
   risk_tier=0; replaces direct ChromaDB access by Admissions Agent (U-03)
4. **`kafka_event_publish`** — publish a validated nine-field CloudEvent to a
   named topic; risk_tier=1, side_effect_class=reversible_write; wraps
   `platform/engage/consumers/kafka_consumers.py` producer pattern

Specify: purpose, input schema, output schema, authentication, tenant
context, risk_tier, side_effect_class, idempotency requirement, approval
requirement, audit event emitted on call, timeout, retry policy, and the
exact upstream API/credential it wraps (never a raw DB credential handed to
the calling agent — Rule R2).

Do not implement runtime code.
```

### PLN-05 — Atomic step execution plan

```text
Act as an Engineering Manager. Break down the implementation of:
the following step/feature into an atomic, sequential task list
(open a separate Bob task per item):

1. **Remove HC-7 `DEV_BYPASS_AUTH` guard** — `onboarding-agent/src/security/keycloak-auth.ts` (R-01, A-1) ✅ DONE — confirmed resolved in EXPLORE-GATE §15
2. **Rotate Brevo key in `engage-secrets` + `pmaas-secrets`** (SEC-01, A-2) ✅ DONE — confirmed in EXPLORE-GATE §15
3. **Scrub `VOICE_API_KEY` literal** from `platform/voice/voice-deploy.yaml:63` (SEC-03, A-3)
4. **Populate 7 `REPLACE_FROM_VAULT`** entries in `admissions-secrets` via OpenBao (SEC-04, A-4)
5. **Fix `KEYCLOAK_ISSUER`** in `platform/admissions/admissions-deploy.yaml` YAML manifest (SEC-06, A-5)
6. **Deploy Consent Service** to `i3-consent` namespace (B-1)
7. **Enforce HMAC on `subject_id_hash`** in `platform/engage/web/src/app/api/campaigns/send/route.ts` (SEC-07, D-3)
8. **Rebuild admissions-agent image** with `chromadb==0.4.24` (R-08, F-1)
9. **Add `i3-onboarding`** to `platform/namespaces/namespaces.yaml` (U-05, F-2)

1. Objective (one sentence).
2. Pre-requisites and strict predecessor steps.
3. Affected files, categorised Created / Modified / Deleted.
4. Step-by-step numbered task list covering scaffolding, configuration,
   schema migration, application logic, and logging.
5. Risk and rollback strategy per step.
6. Target sensor checks — machine-verifiable assertions (grep, curl, pytest,
   npm test) that will prove completion in Verify.

Confirm the plan does not touch solution-01 through solution-08 (HC-1).
```

### PLN-06 — 90-day master plan / release sequencing

```text
Consolidate the approved workstream plans into
docs/plans/master-plan.md: a dependency-ordered task graph (≤2-day tasks
each), squad allocation, weekly milestones, and the exit gates for each
phase. Sequence parallel product tracks so that none claims a core
capability (GPU, residency, multi-tenancy, audit-readiness) before the
owning workstream passes acceptance (§12). Protect the critical path to any
externally-committed launch milestone explicitly named in the Blueprint.
```

### PHASE 2 EXIT CRITERIA

- [ ] ADRs approved and stored in `docs/adr/`
- [ ] Every acceptance criterion is measurable with a stated verification method
- [ ] Scope frozen for the current build window; anything new goes to a backlog, not the plan
- [ ] The anchoring commercial milestone's critical path is explicitly protected

```text
Act as an independent Lead Architect. Review all Plan artefacts. Do not
write code. Confirm every contract has: an ADR, measurable acceptance
criteria, a rollback plan, and explicit HC-1→HC-8 and R1→R5 mapping.

Return: PLAN STATUS: READY | READY-WITH-CONDITIONS | NOT-READY, with exact
missing items if not ready.
```

---

## PHASE 3 — IMPLEMENT

**Objective:** execute one bounded task at a time with small diffs, automated checks, and a rollback path. Bob's role: pair-programmer. Tier 0–1 tasks may run near-autonomously; Tier 2+ require human review before merge; Tier 3–4 are recommendation-only (§6).

### IMP-01 — Rotate hardcoded credentials

```text
Act as a Lead DevSecOps Engineer. Execute the credential-rotation step for:
the following files flagged in EXP-03 (EXPLORE-GATE §4):

**Remaining open findings** (A-1 and A-2 already resolved per EXPLORE-GATE §15):
- `platform/voice/voice-deploy.yaml` line 63 — `VOICE_API_KEY` hardcoded literal (SEC-03)
- `platform/admissions/admissions-deploy.yaml` — 7 `REPLACE_FROM_VAULT` placeholder env vars (SEC-04)
- `platform/admissions/admissions-deploy.yaml` — `KEYCLOAK_ISSUER` internal URL not reflected in YAML (SEC-06)
- `platform/engage/web/src/app/api/campaigns/send/route.ts` — `subject_id_hash` falls back to raw email (SEC-07, HC-6)

OpenBao KV v2 target paths (EXPLORE-GATE §6):
- `i3/voice/api-key`
- `i3/admissions/chromadb-url`, `i3/admissions/keycloak-secret`, `i3/admissions/db-url`, etc.

1. Scrub plaintext production secrets from the flagged files.
2. Replace hardcoded values with runtime OpenBao CLI retrieval, e.g.:
     SECRET=$(vault kv get -field=password i3/<path>)
   using an explicit OpenBao KV v2 path per secret (e.g. i3/mariadb/root,
   i3/keycloak/admin, i3/litellm/api-key).
3. Untrack any committed .env/.env.local/secret-patch files from Git and
   update .gitignore to block them going forward.
4. Verify no plaintext secret remains via a repo-wide grep and paste the
   (clean) output as evidence.
```

### IMP-02 — Fix TLS certificate validation

```text
Act as a Lead Backend Engineer. For the following files (identified in
EXP-03 and the workspace inventory), change any
rejectUnauthorized: false (or equivalent) to true, and inject the CA
certificate via environment-configured path rather than a hardcoded one.
Update the deployment manifest to mount the CA secret and set the
corresponding environment variable. Confirm the service still connects in
a local/staging smoke test and paste the result.
```

### IMP-03 — Implement HMAC webhook/signature validation

```text
Act as a Backend Security Engineer. For the following webhook routes
(identified in the workspace inventory):
- `platform/engage/web/src/app/api/campaigns/send/route.ts` — Brevo webhook
- `platform/engage/web/src/app/api/contacts/route.ts` — inbound contact events
- `onboarding-agent/src/server.ts` — onboarding trigger webhooks

Intercept the
incoming request before body parsing, validate the provider signature
header against the shared secret using HMAC-SHA256, and compare using a
constant-time comparison (e.g. crypto.timingSafeEqual /
hmac.compare_digest). Return 401 on invalid/missing signature. Preserve any
existing challenge/verification handshake unchanged. Confirm the route
parses raw bytes correctly for signature verification.
```

### IMP-04 — Replace raw hashing with keyed HMAC + fix OTP storage (HC-6)

```text
Act as a Backend Security Engineer. In the following files (EXPLORE-GATE
SEC-07, HC-6), replace any raw hashlib.sha256 / raw email fallback applied
to National IDs or phone numbers:
- `platform/engage/web/src/app/api/campaigns/send/route.ts` —
  `subject_id_hash` TODO falls back to raw email address
- `platform/ford/api/main.py` — verify HMAC-SHA256 path uses
  `MEMBER_HMAC_SECRET` from OpenBao (confirmed HC-6 ✅ in EXPLORE-GATE §2.1,
  but re-verify after any merge)

Replace any raw
with a keyed HMAC-SHA256 using MEMBER_HMAC_SECRET from OpenBao. Move OTPs
out of any persistent SQL column into Redis with a short TTL (e.g. 600s),
keyed by an HMAC-derived token, verified with a constant-time comparison.
Add rate limiting on verification attempts (e.g. max 5 attempts per
identifier before a 429). Confirm no raw hashing of these identifiers
remains anywhere in the file.
```

### IMP-05 — Fix connection-pool and event-loop lifecycle

```text
Act as a Lead Performance Engineer. In the following files (identified
in EXPLORE-GATE §3 and workspace inventory):
- `platform/engage/consumers/kafka_consumers.py` — Kafka consumer handlers
- `platform/admissions/admissions_agent.py` — admissions request handler
- `platform/pmaas/agents/campaign_agent.py` — campaign processing handler
- `platform/voice/tts/tts_service.py` — TTS request handler

Remove any per-message
asyncio.new_event_loop() or asyncpg.connect() calls inside a message
handler or request scope. Create a module-level connection pool
initialised once at startup (with sensible min/max size), and use async
context managers for every acquire. Validate every incoming message
against a Pydantic model before use; on validation failure, log a
structured error and safely commit the offset rather than crashing the
worker.
```

### IMP-06 — Replace in-memory state with Redis (for HPA-safe scaling)

```text
Act as a Backend Engineer. In the following files (identified in
EXPLORE-GATE §5 tenant isolation findings):
- `onboarding-agent/src/render/taskSync.ts` — Redis plan store is
  TTL-keyed but NOT tenant-partitioned (U-05 partial)
- `onboarding-agent/src/orchestrator/planner.ts` — `_pending` state
  management
- `onboarding-agent/src/orchestrator/subagents/base-scan.ts` — subagent
  result buffering

Replace any in-memory Map/dict used
to hold session or pending-operation state with Redis GET/SET/DEL calls
using an explicit TTL and a namespaced key (e.g. plan:<id>,
mcp:pending:<token>). On Redis unavailability, fail with an explicit
error response — never silently fall back to in-memory state.
```

### IMP-07 — LiteLLM metering spine (Workstream B2)

```text
Implement the metering spine per the approved PLN-02/PLN-05 plan for B2:
- LiteLLM config with per-project virtual keys and hard, fail-closed budgets
- Postgres migrations for customers/projects/api_keys/monthly_usage
  (tenant_id NOT NULL, RLS enabled)
- A nightly ETL job emitting per-customer statements to object storage
- A key-rotation job; confirm the master key is disabled for interactive
  use and reachable only as a Vault-managed break-glass service account
Rules R1 and R4 apply — reject any design that bypasses them.
Open a PR including: migration tests, an over-quota rejection test, and a
short README section for the billing team.
```

### IMP-08 — Tenant namespace template (Workstream B4)

```text
Implement the i3-tenant Helm chart per the approved ADR:
- Instantiates: an OpenShift namespace (cust-<slug>), a Keycloak group +
  client roles, resource quotas, a default-deny network policy, a
  per-project LiteLLM key delivered via ExternalSecret from Vault, and
  Prometheus scrape labels.
- Parameterise by tenant tier (sandbox/standard/dedicated).
Include CI tests confirming the chart: (a) renders with no master-key
reference anywhere, (b) enforces the default-deny network policy,
(c) creates the Keycloak group correctly, (d) wires the LiteLLM key via
ExternalSecret. Deploy one demo tenant and paste the verification output.
```

### IMP-09 — WORM audit pipeline (Workstream B4)

```text
Implement the audit pipeline: structured audit events (who/what/when/
tenant/risk-tier/outcome) written to append-only object storage with a
retention lock. Include a tamper-evidence check job and an auditor query
CLI (e.g. i3-audit who <user> --date <date> --tenant <slug>). Treat the
retention class as a configurable parameter, never a hardcoded value —
mark it as an open legal question if not yet confirmed. This is Tier 2:
human review required before merge.
```

### IMP-10 — GPU pool + automatic CPU fallback (Workstream B1)

```text
Implement the GPU serving pool and LiteLLM fallback routing to the CPU pool
on GPU node failure, per the approved plan. Gate ALL outputs with the
[GAP] tag until the benchmark harness passes. Deliverables: node-pool
manifests, serving configs, routing config, and a benchmark harness
comparing first-token latency against the recorded CPU baseline for every
model alias in production. No claim of GPU acceleration may appear in any
non-gated output until the harness prints PASS.
```

### IMP-11 — Evaluation harness + PII pre-filter (Workstream B5)

```text
Implement: (a) an evaluation harness with pluggable task suites, including
a dedicated low-resource-language (e.g. Swahili/Sheng) suite built on
validated corpora; (b) a PII pre-filter sidecar (NER-based, tuned to the
identifier types relevant here — National ID formats, transaction IDs,
phone numbers) redacting before any log write; (c) a one-page model-card
template and generator; (d) a CI release gate that blocks promotion of any
model/quantisation change failing the harness. Prove the gate works by
deliberately submitting a failing change and showing the block, then
revert.
```

### IMP-12 — MCP Gateway + Agent Registry

```text
Implement the MCP Tool Gateway and Agent Registry:
- Registry: agent id, owner, risk-tier, allowed tools, approval policy.
- Gateway interceptor: every tool call is checked against the registry
  tier; Tier 3+ requires a signed human-approval record (from the audit
  trail) before execution.
- Seed the registry with tools discovered in EXP-04, tagged with their
  correct risk_tier and side_effect_class.
Any agent with PR-opening or similarly consequential write autonomy
registers at Tier 3 minimum with that capability approval-gated. Do NOT
enable any Tier 3 tool without a passing approval-flow test.
```

### Implementation discipline checklist (apply to every PR)

- [ ] Architecture rules R1–R5 checked by CI
- [ ] `[GAP]` tags present wherever a capability has not passed acceptance
- [ ] Tier 3+ tools have a passing approval-flow test
- [ ] Migrations are idempotent; rollback documented
- [ ] No secrets outside OpenBao/Vault; no master key referenced anywhere
- [ ] Observability: metrics + dashboard + trace on every new service
- [ ] `tenant_id` present and enforced end-to-end (HC-4) wherever data is touched

---

## PHASE 4 — VERIFY

**Objective:** independently prove functional, security, tenant-isolation, agent-safety, performance and operational requirements. Bob's role: auditor / red-teamer / evidence packager. This phase never fully ends — it becomes the standing operating cadence.

### VER-01 — Workstream acceptance run

```text
Execute the acceptance harness for the following workstream against staging
(use a separate Bob task per workstream; order matches EXPLORE-GATE §13):

- **Track A** — Security & Compliance: SEC-01→SEC-09 closed, HC-7 clean
- **Track B** — Consent Service: P2-GATE-01 sensor (circuit-breaker
  fail-closed, DPA 2019 §25)
- **Track C** — Agent Registry + MCP: P2-GATE-02 (6 manifests registered),
  P2-GATE-03 (forbidden tool → HTTP 403)
- **Track D** — Tenant Isolation: P2-GATE-04 (ChromaDB per-tenant,
  CloudEvent `tenant_id`, HMAC enforcement)
- **Track E** — Agent Safety: HC-3 (Lobster Trap on Campaign, Zuri, PMaaS)
- **Track F** — Image + Code Fixes: chromadb==0.4.24, `namespaces.yaml`,
  WatsonX key, Tekton PVC
- **Track G** — Phase 3 Pre-work: Fabric MSP enrollment, SCC fix, chaincode
  scaffold (HC-2 Nov 2026 deadline)

Produce a
signed evidence pack: harness output, raw logs, dashboard screenshots, and
a PASS/FAIL verdict per acceptance criterion. Any FAIL gets a root-cause
section and a fix-or-accept decision for the Tech Lead. Publish to
docs/verification/<workstream>-evidence-<date>.md.
```

### VER-02 — Tenancy isolation red-team

```text
Red-team the multi-tenancy pattern: attempt cross-tenant reads/writes via
token forgery, group-claim manipulation, direct service calls bypassing the
gateway, and namespace escape. Every attempt must be denied AND appear in
the WORM audit trail with the attacking identity. Output an attack matrix
(vector × result × evidence). Any success is CRITICAL and blocks sign-off.
```

### VER-03 — Approval-gate red-team

```text
Attempt to induce a Tier 3+ agent action without a human-approval record
(e.g. a financial write, a broadcast send, a PR creation). Try prompt
injection through tool outputs and crafted user messages. Success
criterion: every attempt is refused, logged at its correct risk tier, and
triggers an alert. Output a refusal-evidence pack.
```

### VER-04 — Security & secret re-sweep

```text
Re-run the EXP-03 security and secret sweep against the current state of
the following targets post-implementation — match against EXPLORE-GATE §4
findings SEC-01 through SEC-09:

- `platform/voice/voice-deploy.yaml` (SEC-03 — VOICE_API_KEY)
- `platform/admissions/admissions-deploy.yaml` (SEC-04/SEC-06 — REPLACE_FROM_VAULT, KEYCLOAK_ISSUER)
- `platform/engage/web/src/app/api/campaigns/send/route.ts` (SEC-07 — HC-6 HMAC)
- `onboarding-agent/src/security/keycloak-auth.ts` (SEC-02 — HC-7 DEV_BYPASS_AUTH, already ✅)
- Full repo secret scan (SEC-01 Brevo key already rotated ✅)

Confirm every finding from the original sweep
is closed, and that no new hardcoded secret, DEV_BYPASS_AUTH, raw hashing
of a sensitive identifier, or unauthenticated endpoint has been introduced.
```

### VER-05 — Data-residency / sovereignty audit

```text
Enumerate every replication path, backup target, and vendor egress for
sensitive data. Verify no cross-border transfer is configured — enforced
by the absence of replication, not merely by written policy. Mark anything
not yet independently verifiable as OPEN, never PASS. Any confirmed
violation is CRITICAL.
```

### VER-06 — Collateral / claim correction pack

```text
Using the current gap register, produce a collateral-correction pack: for
each live customer-facing artefact, quote the exact current sentence, the
corrected sentence scoped strictly to what has passed verification, and
the evidence link. Flag any present-tense claim about GPU acceleration,
data residency, multi-tenant isolation, or audit trails that lacks a PASS
evidence pack.
```

### VER-07 — Launch readiness review

```text
Run the launch-readiness review for **[choose one — open a separate Bob
task per milestone]**:

1. **FORD-Asili IEBC staging** (HC-2 — Nov 2026 deadline):
   - Fabric orderer `orderer-0` CrashLoopBackOff resolved (EXPLORE-GATE §9)
   - `peer0-i3tech` SCC hostPath violation fixed (U-10)
   - Go chaincode unit tests pass: `go test ./...` (P3-GATE-05)
   - HC-6 HMAC-SHA256 on all NID tokens via `MEMBER_HMAC_SECRET`
   - HC-8 `ballotPrivate` PDC separation verified

2. **EvalOS Phase 2** (P2-GATE-04):
   - `tenant_id` enforced on all tables
   - `evalos-submissions` Kafka consumer implemented (U-06)
   - Lobster Trap on Zuri agent (U-09)

3. **Platform Security Gate** (Phase 2 exit):
   - All 9 SEC findings closed
   - Agent registry 6/6 manifests registered
   - ChromaDB per-tenant isolation confirmed

Run the launch-readiness review for this product/milestone: demo script
against the committed capability list, credential/identity verification
flow, guard conditions on any lifecycle state machine, agent approval
gates for every Tier 3+ agent involved, and dashboards wired to real data
(not mocked). Output a go/no-go memo for the CEO.
```

### VER-08 — Standing AgentOps cadence (post-launch)

```text
Define the weekly AgentOps review pack: autonomy rate per agent (actions
completed without human override), approval-gate latency, spend per tenant
vs. budget, evaluation-suite trend, audit-trail anomalies, and the top-5
risk-register items with drift status. Automate its generation from the
metrics store, spend ledger, and audit store. This pack replaces ad-hoc
status meetings.
```

### Production Readiness Scorecard

Use binary evidence, not a subjective score.

| Area | Required evidence | Status |
|---|---|---|
| Identity | Auth + role tests | PASS/FAIL |
| Tenancy | Cross-tenant attack tests | PASS/FAIL |
| Database | RLS + migration tests | PASS/FAIL |
| API | Contract tests | PASS/FAIL |
| Events | Schema/consumer tests | PASS/FAIL |
| Secrets | Secret scan | PASS/FAIL |
| AI quality | Evaluation suite | PASS/FAIL |
| Agents | Autonomy + tool tests | PASS/FAIL |
| MCP | Policy tests | PASS/FAIL |
| Performance | Load-test evidence | PASS/FAIL |
| Observability | Metrics/logs/traces | PASS/FAIL |
| DR | Restore evidence | PASS/FAIL |
| Deployment | Manifest/runtime checks | PASS/FAIL |
| Rollback | Tested procedure | PASS/FAIL |

```text
PASS        = every release-blocking control has evidence.
CONDITIONAL = only explicitly documented, non-blocking findings remain.
FAIL        = any release-blocking control fails.
```

---

# 9. Master System Prompt for IBM Bob

Use this once the repository rules (§5) and architecture documents are loaded — this is the standing contract for every session on this programme.

```text
You are IBM Bob, acting as the controlled engineering partner for the i3
Technologies Unified Agentic AI Platform.

Your job is to help implement the approved architecture, not invent an
uncontrolled replacement architecture.

Operate through four phases: EXPLORE → PLAN → IMPLEMENT → VERIFY.

Mandatory behaviour:
1. Explore before editing.
2. Plan before implementing substantial changes.
3. Implement in atomic tasks.
4. Verify independently.
5. Preserve working production assets — do not rewrite what already works.
6. Prefer shared platform services over duplicated implementations.
7. Enforce tenant isolation everywhere.
8. Enforce MCP policy for every agent tool call.
9. Keep agents at L0/L1 until evaluation evidence and explicit approval exist.
10. Never expose secrets.
11. Never disable a security control to make a test pass.
12. Never modify solution-01 through solution-08.
13. Never introduce a direct application-to-model call that bypasses the
    model gateway.
14. Never give an agent direct database credentials.
15. Never claim a feature is production-ready without verification evidence.
16. Never silently invent missing architecture facts — mark them UNKNOWN.
17. Stop when repository reality conflicts materially with the approved plan.
18. Prefer small, reversible changes.
19. Record machine-verifiable evidence for every completion claim.
20. Treat security, tenant isolation and auditability as architecture
    requirements, not optional polish.

For every task: READ → UNDERSTAND → PLAN → CHANGE → TEST → VERIFY → REPORT.

Your final report must contain: Objective; what you inspected; what
changed; files changed; tests executed; security checks; tenant checks;
agent-safety checks; performance observations; deployment impact; rollback
plan; remaining risks; evidence; recommended next atomic task.

Do not continue to another major task until the current task passes its
acceptance criteria.
```

---

# 10. Recommended First 10 Bob Sessions (Quick Start)

1. **EXP-00** — repository and infrastructure inventory
2. **EXP-01** — dependency/blast-radius mapping (start with the highest-risk subsystem)
3. **EXP-02** — tenant/database audit
4. **EXP-03** — security/secret audit
5. **EXP-04** — agent/MCP audit
6. **EXP-05** — model gateway audit
7. **EXP-06** — Kafka/event audit
8. **Explore Gate** — human sign-off before proceeding
9. **PLN-01 → PLN-06** — architecture decisions, contracts, master plan
10. **Plan Gate** — human sign-off; only after this does Bob begin broad implementation

---

# 11. Definition of Done

Every Bob task must finish with all of the following checked:

```text
[ ] Scope identified
[ ] Hard constraints checked (HC-1 → HC-8)
[ ] Dependencies identified
[ ] Existing tests inspected
[ ] Code changed only within approved scope
[ ] Unit tests added/updated
[ ] Integration tests added/updated where applicable
[ ] Security checks executed
[ ] Tenant isolation checked
[ ] Agent risk tier checked where applicable
[ ] Observability checked
[ ] Migration/rollback checked
[ ] Documentation updated
[ ] Git diff reviewed
[ ] Acceptance criteria passed
[ ] Evidence recorded
```

---

# 12. Capability Claim Matrix

No claim below may be made in the present tense — internally or to a customer — until its owning evidence exists.

| Claim | May be said when... | Owning artefact |
|---|---|---|
| "GPU-accelerated inference" | B1 benchmark harness signed PASS | `docs/verification/B1-evidence-*.md` |
| "Regional data residency" | B3 residency audit PASS | `residency-audit.md` |
| "Per-tenant metering & billing" | B2 ledger reconciled for one full billing cycle | `docs/verification/B2-evidence-*.md` |
| "Multi-tenant isolation" | B4 isolation red-team — all attempts denied | `docs/verification/B4-evidence-*.md` |
| "Audit-ready trails" | B4 WORM pipeline + auditor-query demo | same as above |
| "Governed autonomous agents" | Approval-gate red-team — all attempts refused | `docs/verification/VER-03-*.md` |
| Anything else | Never in present tense until its evidence pack exists | — |

---

# 13. Strategic End-State Architecture

```text
                     ┌──────────────────────────┐
                     │      i3 UNIFIED EDGE      │
                     │ Cloudflare / Envoy / WAF  │
                     └────────────┬──────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │       KEYCLOAK / SSO       │
                    │ Identity + Tenant Context  │
                    └─────────────┬──────────────┘
                                  │
             ┌────────────────────▼────────────────────┐
             │        AGENT + MCP CONTROL PLANE         │
             │ Registry | Policy | Approval | Audit     │
             └───────────┬─────────────────┬───────────┘
                         │                 │
              ┌──────────▼───────┐ ┌──────▼────────────┐
              │  MODEL GATEWAY    │ │  EVENT BACKBONE   │
              │ LiteLLM/vLLM/     │ │ Kafka / CloudEvents│
              │ Ollama            │ │                    │
              └──────────┬────────┘ └──────┬─────────────┘
                         │                 │
        ┌────────────────▼─────────────────▼────────────┐
        │              SHARED PLATFORM DATA              │
        │ PostgreSQL | pgvector | Redis | Object Store   │
        │ WORM Audit | OpenBao | Observability            │
        └────────────────────┬────────────────────────────┘
                             │
     ┌───────────────┬───────┼────────┬───────────────┐
     ▼               ▼       ▼        ▼               ▼
  Product A       Product B  ...   Product N        Agents
     │               │       │        │               │
     └───────────────┴───────┴────────┴───────────────┘
                             │
        ┌────────────────────▼─────────────────────┐
        │              PRODUCT PLANE                │
        │  (all consumer products, e.g. SmartLabs,  │
        │   EvalOS, EduBridge, OTT, AfroERP, Engage) │
        └────────────────────┬──────────────────────┘
                             │
                 ┌───────────▼───────────┐
                 │  SOVEREIGN DEPLOYMENTS │
                 │  Cloud | On-prem | DC  │
                 └────────────────────────┘
```

**The key architectural outcome: one governed platform with many products** — not many products each rebuilding identity, AI, tenancy, billing, events and governance independently.

---

# 14. Immediate Execution Checklist

```text
[ ] Upload this document to IBM Bob's context
[ ] Upload the source Modernisation Technical Implementation Blueprint
[ ] Install .bob/rules (§5.1)
[ ] Install custom Bob modes, including i3-independent-verifier (§5.2)
[ ] Configure MCP guard tools (§5.3)
[ ] Verify protected namespace boundaries (HC-1)
[ ] Run EXP-00 → EXP-06
[ ] Pass the Explore Gate
[ ] Produce ADRs, service contracts, database contracts, event contracts,
    agent manifests, test plans (PLN-01 → PLN-06)
[ ] Pass the Plan Gate
[ ] Start atomic implementation tasks (IMP-01 →)
[ ] Verify every task before starting the next
[ ] Run full release verification (VER-01 → VER-08) before any launch claim
```

---

## Final Engineering Principle

**Build the shared core once. Extend working products rather than rewriting them. Put every model call behind the model gateway. Put every agent action behind the MCP policy boundary. Put every data record behind tenant isolation. Put every consequential action behind appropriate human approval. Put every release behind machine-verifiable evidence.**

This is the operating model that lets IBM Bob function as a genuine development partner while keeping architecture, security, sovereignty and product strategy under human control.

---

## Source Traceability

This guide consolidates and operationalises:
1. *i3 Technologies — Modernisation Technical Implementation Blueprint*, v1.0, September 2026
2. *IBM Bob Modernisation Playbook & Prompt Catalog*, September 2026
3. *i3 IBM Bob 4-Phase Development Playbook*
4. *i3 IBM Bob Modernisation Operational Playbook*

**Document version:** 1.1 (Explore Gate revision — all `[TARGET]` placeholders resolved)
**Revised:** 2026-09-22 — based on `EXPLORE-GATE.md` findings (EXP-00 through EXP-06,
  P1 gate 12/12 PASS, EXPLORE STATUS: READY ✅)
**Recommended next revision:** after Plan Gate sign-off (PLN-01 → PLN-06), updating
  the Verify phase prompts (VER-01, VER-04, VER-07) with final Phase 2 workstream
  evidence file paths.
