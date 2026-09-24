# ADR-002: Agent Registry Full Manifest Seeding

**Status:** Proposed  
**Date:** 2026-09-22  
**Deciders:** i3 Platform Engineering Lead, AI Safety Lead, Autonomy Review Board  
**Relates to:** EXPLORE-GATE §13 Track C (C-1, C-2, C-3), P2-GATE-02  
**Supersedes:** — (no prior ADR; agents operated without a formal registry)

---

## Context

### Problem Statement

The i3 AI Platform hosts 5 active AI agents plus 1 planned (FORD):

| Agent | Namespace | Runtime | Autonomy Tier | Registry State |
|-------|-----------|---------|--------------|---------------|
| Admissions Agent (Nuru) | i3-admissions | Python/FastAPI | L1 | Not registered |
| Campaign Agent | i3-pmaas | Python/FastAPI | L1 | Not registered |
| Onboarding Agent | i3-onboarding | TypeScript/Express | L0/L1 | Not registered |
| EvalOS Zuri | i3-evalos | Python/FastAPI | L1 | Not registered |
| PMaaS Agent | i3-pmaas | Python/FastAPI | L1 | Not registered |
| FORD Election Agent | i3-ford | Python/FastAPI | L0 | Not registered |

The Agent Registry service is **deployed** (Running, port 8200, `i3-agent-mesh`) and its
`POST /agents` / `GET /agents` API is operational. However, **zero agent manifests have been
seeded** (EXPLORE-GATE §13 C-1). The P2-GATE-02 sensor requires `GET /agents` to return exactly
6 manifests.

Without populated manifests:
- The MCP gateway cannot validate that a calling agent's tool invocation is in its `allowed_tools`
  list (ADR-003 depends on this).
- HC-3 compliance cannot be audited: there is no machine-readable record of each agent's autonomy
  tier, allowed tools, and cost budget.
- Kong API Gateway (ADR-002 of the execution plan, STEP-P2-07) cannot enforce per-agent rate limits
  without a canonical `agent_id` → `rate_limit` mapping from the registry.
- The `agent_decision_log` lacks a foreign key–validated `agent_id`, so decision attribution is
  unreliable.

### Explore-Phase Evidence

From EXPLORE-GATE §6 (Agent Safety Findings):
- Admissions Agent: HC-3 compliant (Lobster Trap + MCP gateway integration confirmed)
- Campaign Agent: **No prompt firewall** (ADR-006 addresses this separately)
- EvalOS Zuri: **No firewall confirmed** (ADR-006)
- PMaaS Agent: **No firewall confirmed** (ADR-006)
- Onboarding Agent: HC-3 compliant (lobster-trap.ts + planner-gated tool calls)

The registry manifests must accurately reflect each agent's **current** tool permissions and
autonomy tier as discovered. They are not aspirational: a manifest does not promote an agent to
a higher autonomy level — it formalises what the platform enforces today.

---

## Decision

**Seed all 6 agent manifests into the Agent Registry via declarative YAML files committed to
`platform/agent-registry/manifests/`, applied to the running registry at deploy time.**

Each manifest declares:
- `agent_id` (stable slug, lowercase-hyphen)
- `name` (human-readable)
- `version` (semver)
- `autonomy_tier` (L0 | L1 — never L2 or L3 without evaluation evidence per HC-3)
- `allowed_tools` (explicit allow-list; all other tools are implicitly forbidden)
- `forbidden_tools` (explicit deny-list for clarity on high-risk tools)
- `cost_budget_tokens` (per-session token ceiling, enforced by LiteLLM virtual key)
- `guardrail_policy` (Lobster Trap version reference)
- `owner` (team responsible)
- `state` (active | suspended | retired)

The registry service loads manifests from `/app/manifests/*.yaml` at startup via a seeding
script (`seed_manifests.py`) that calls `POST /agents` for each file. This is idempotent:
re-applying an existing manifest PATCH-updates it rather than creating a duplicate.

---

## Agent Manifests (Normative)

### admissions-agent-v1 (Nuru Admissions Assistant)
```yaml
agent_id: admissions-agent-v1
name: Nuru Admissions Assistant
version: "1.0.0"
autonomy_tier: L1
allowed_tools:
  - chroma.search
  - litellm.chat
  - admissions_db.read
  - consent.check
forbidden_tools:
  - admissions_db.write
  - kafka.produce
  - brevo.send
cost_budget_tokens: 50000
guardrail_policy: lobster-trap-v1
owner: i3-technologies/admissions-team
state: active
```

### campaign-agent-v1
```yaml
agent_id: campaign-agent-v1
name: Campaign Personalisation Agent
version: "1.0.0"
autonomy_tier: L1
allowed_tools:
  - litellm.chat
  - kafka.produce            # engage.campaign-trigger only
  - consent.check
forbidden_tools:
  - admissions_db.read
  - admissions_db.write
  - postgres.members.write
cost_budget_tokens: 20000
guardrail_policy: lobster-trap-v1   # pending ADR-006 implementation
owner: i3-technologies/pmaas-team
state: active
```

### onboarding-agent-v1
```yaml
agent_id: onboarding-agent-v1
name: Onboarding Orchestration Agent
version: "1.0.0"
autonomy_tier: L1
allowed_tools:
  - litellm.chat
  - admissions_db.read
  - redis.plan_store
  - keycloak.user_read
forbidden_tools:
  - kafka.produce
  - postgres.members.write
  - brevo.send
cost_budget_tokens: 75000
guardrail_policy: lobster-trap-v1
owner: i3-technologies/admissions-team
state: active
```

### evalos-zuri-v1
```yaml
agent_id: evalos-zuri-v1
name: Zuri Study Coach
version: "1.0.0"
autonomy_tier: L1
allowed_tools:
  - litellm.chat
  - evalos_db.read
  - consent.check
forbidden_tools:
  - evalos_db.write
  - kafka.produce
  - postgres.members.write
cost_budget_tokens: 30000
guardrail_policy: lobster-trap-v1   # pending ADR-006 implementation
owner: i3-technologies/evalos-team
state: active
```

### pmaas-agent-v1
```yaml
agent_id: pmaas-agent-v1
name: PMaaS Briefing Agent
version: "1.0.0"
autonomy_tier: L1
allowed_tools:
  - litellm.chat
  - pmaas_db.read
  - consent.check
forbidden_tools:
  - pmaas_db.write
  - kafka.produce
  - postgres.members.write
cost_budget_tokens: 40000
guardrail_policy: lobster-trap-v1   # pending ADR-006 implementation
owner: i3-technologies/pmaas-team
state: active
```

### ford-election-agent-v1
```yaml
agent_id: ford-election-agent-v1
name: FORD Election Registration Agent
version: "0.1.0"         # pre-production; Fabric orderer not live
autonomy_tier: L0         # human-in-loop required for all ballot actions
allowed_tools:
  - fabric.query           # read-only ledger queries
  - consent.check
forbidden_tools:
  - fabric.invoke          # state-modifying chaincode calls; forbidden at L0
  - kafka.produce
  - postgres.members.write
cost_budget_tokens: 10000
guardrail_policy: lobster-trap-v1
owner: i3-technologies/ford-team
state: suspended           # orderer CrashLoopBackOff — EXPLORE-GATE §9
```

---

## Alternatives Considered

### A1 — Hard-code agent metadata in each service's environment variables
**Rejected.** Duplicates the manifest across 6 independent deployments. No single source of truth.
HC-3 audit requires a central authoritative record; env vars are not auditable.

### A2 — Store manifests only in the registry PostgreSQL table, no YAML files
**Rejected.** YAML files committed to git provide an auditable change history (git blame, PR review)
for every autonomy tier change or allowed-tool addition. Database-only records can be mutated
without a paper trail.

### A3 — Use Kubernetes CRDs (Custom Resource Definitions) to define agents
**Deferred to Phase 4.** CRDs provide stronger schema enforcement and Kubernetes-native RBAC.
However, they require cluster-level CRD installation and an operator. The YAML+HTTP pattern is
sufficient for Phase 2 and can be migrated to CRDs non-destructively.

### A4 — Register agents at the L2 autonomy tier for Campaign Agent and PMaaS Agent
**Rejected.** HC-3 forbids promotion beyond L1 without verified evaluation evidence. Neither
Campaign Agent nor PMaaS Agent has RAGAS evaluation evidence for autonomous operation.

---

## Technical Drivers

| Driver | Detail |
|--------|--------|
| HC-3 compliance | Every manifest's `autonomy_tier` is machine-readable and enforced by the MCP gateway |
| Auditability | YAML files in git provide full change history for autonomy tier promotions |
| MCP gateway dependency | ADR-003 (MCP gateway) cannot enforce tool allow-lists without populated manifests |
| Cost control | `cost_budget_tokens` maps to LiteLLM virtual key budget; overage returns 429 |
| Decision log fidelity | `agent_decision_log.agent_id` references the registry's canonical `agent_id` slug |

---

## Security Implications

| # | Implication |
|---|------------|
| SEC-1 | Manifest `state: suspended` prevents the MCP gateway from accepting tool calls from that agent. FORD election agent is suspended while Fabric orderer is in CrashLoopBackOff. |
| SEC-2 | `forbidden_tools` list is advisory for human readers; the MCP gateway enforces the `allowed_tools` allow-list. An absent tool = forbidden. |
| SEC-3 | Autonomy tier changes (e.g., L1 → L2) require a PR with evaluation evidence attached. The registry API `PATCH /agents/{id}/state` for tier changes requires `autonomy:admin` Keycloak role. |
| SEC-4 | Registry service has no external route via Kong; it is accessible only from within the cluster. Agent decision log is read-only from outside `i3-agent-mesh`. |

---

## Multi-Tenancy Implications

- The Agent Registry is a **platform-level** service — manifests are not tenant-scoped (agents serve
  all tenants, with per-request `tenant_id` passed in the decision log).
- `agent_decision_log.tenant_id UUID NOT NULL` — every decision is attributed to the tenant whose
  session triggered it.
- Cost budget (`cost_budget_tokens`) is per-session, not per-tenant; per-tenant budget enforcement
  is handled by LiteLLM virtual keys (Phase 3 STEP-P3-01).

---

## Agent-Autonomy Implications

- **No agent may operate at L2 or above** without a separate ADR + evaluation evidence. This ADR
  caps all 6 agents at L1 (or L0 for FORD).
- The FORD election agent is set to `state: suspended` — this is not a permanent status; it will
  transition to `active` after the Fabric orderer is remediated (EXPLORE-GATE §9, Phase 3).
- Future promotion of any agent from L1 → L2 requires: RAGAS faithfulness ≥ 0.90, red-team
  promptfoo pass rate ≥ 95%, and explicit Autonomy Review Board sign-off per HC-3.

---

## Data Implications

### agent_decision_log DDL

```sql
CREATE TABLE agent_decision_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,          -- HC-4
  agent_id        TEXT NOT NULL,          -- references agents.agent_id
  session_id      TEXT,
  autonomy_tier   TEXT NOT NULL CHECK (autonomy_tier IN ('L0','L1','L2','L3')),
  model           TEXT,
  input_tokens    INT,
  output_tokens   INT,
  cost_usd        NUMERIC(10,6),
  tools_invoked   TEXT[],
  policy_decision TEXT CHECK (policy_decision IN ('allowed','blocked','escalated')),
  outcome         TEXT CHECK (outcome IN ('success','error','timeout')),
  human_approver  TEXT,
  correlation_id  UUID,
  causation_id    UUID,
  timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata        JSONB
);
CREATE INDEX ON agent_decision_log (tenant_id, agent_id, timestamp DESC);
ALTER TABLE agent_decision_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON agent_decision_log
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

---

## Event Implications

Each agent emits a `com.i3.agent.decision` CloudEvent (HC-4 envelope with `tenant_id`) to the
`agent-decisions` Kafka topic after every LLM call. This topic is consumed by the Agent Registry
service to populate `agent_decision_log`. The CloudEvent schema:

```json
{
  "specversion": "1.0",
  "type": "com.i3.agent.decision",
  "source": "/agents/{agent_id}",
  "id": "{correlation_id}",
  "tenant_id": "{tenant_id_uuid}",
  "data": {
    "agent_id": "admissions-agent-v1",
    "session_id": "...",
    "autonomy_tier": "L1",
    "model": "granite-nano",
    "input_tokens": 512,
    "output_tokens": 128,
    "cost_usd": 0.000032,
    "tools_invoked": ["chroma.search", "litellm.chat"],
    "policy_decision": "allowed",
    "outcome": "success"
  }
}
```

---

## Operational Implications

| Concern | Mitigation |
|---------|-----------|
| Registry downtime | Decision log emission is fire-and-forget (non-blocking httpx.post with timeout=2s). Agent functionality is unaffected if registry is temporarily unavailable. |
| Manifest drift | `seed_manifests.py` runs at ArgoCD sync time; any committed YAML change is automatically applied within 3 minutes. |
| Suspended agent attempts tool call | MCP gateway returns 403 `{ "error": "agent state: suspended" }`. Logged in `agent_decision_log` with `policy_decision: blocked`. |

---

## Performance Implications

- Decision log emission: 1 async POST per LLM call, timeout 2s, non-blocking. No latency impact on
  agent response path.
- Manifest lookup at MCP gateway: cached in Redis (key: `manifest:{agent_id}`, TTL 60s). Cache miss
  is a single DB read (~5ms).

---

## Cost Implications

- Agent Registry service: 1 replica, 256Mi / 250m CPU.
- `agent_decision_log` table: ~500 rows/day at current traffic → ~25MB/year. Partition by month in
  Phase 3.

---

## Rollback Strategy

1. If a manifest is incorrect, update the YAML file and trigger ArgoCD sync — idempotent.
2. To suspend an agent immediately: `PATCH /agents/{id}/state` with `{ "state": "suspended" }`.
   This does not require a manifest file change and takes effect in < 60s (Redis TTL expiry).
3. Registry database can be rolled back independently without affecting any agent's runtime
   behaviour (decision log emission simply fails silently until registry is restored).

---

## HC-1 through HC-8 Mapping

| Constraint | Mapping |
|-----------|---------|
| HC-1 | No change to solution-01 through solution-08 namespaces. |
| HC-2 | FORD election agent manifest declares `state: suspended` and `autonomy_tier: L0` pending Fabric orderer remediation — does not block IEBC timeline. |
| HC-3 | All 6 agents capped at L0/L1 in manifests. Autonomy tier is machine-readable and enforced by MCP gateway. Promotion path documented above. |
| HC-4 | `agent_decision_log.tenant_id UUID NOT NULL`; CloudEvent envelope includes `tenant_id`. |
| HC-5 | Agent manifests define the policy that the MCP gateway enforces. No agent bypasses the gateway for state-modifying tools. |
| HC-6 | No NID or phone data in agent manifests or decision logs. |
| HC-7 | No auth bypass in registry service or seed scripts. |
| HC-8 | FORD election agent at L0 with `fabric.invoke` in `forbidden_tools` — no ballot state mutation possible without human approval. |

---

## Compliance / Statutory Mapping

| Requirement | How This ADR Satisfies It |
|------------|--------------------------|
| Kenya DPA 2019 §25 — lawful basis | Agent decision log provides evidence of purpose-limited processing per agent |
| Kenya DPA 2019 §50 — automated decision-making | L1 agents with human oversight; L0 (FORD) requires explicit human action |
| IEBC Act Cap. 7A — voter data purpose limitation | FORD agent manifest explicitly forbids state-modifying Fabric calls at L0 |
| ISO 27001 — A.12.4 — logging and monitoring | `agent_decision_log` provides audit trail of all AI-driven decisions |

---

## Acceptance Criteria

```
AC-1: GET /agents → 200 with array of exactly 6 manifest objects
AC-2: GET /agents/admissions-agent-v1 → 200 with autonomy_tier: "L1"
AC-3: GET /agents/ford-election-agent-v1 → 200 with state: "suspended"
AC-4: No manifest has autonomy_tier "L2" or "L3"
AC-5: MCP gateway rejects tool call from suspended ford-election-agent-v1 → 403
AC-6: MCP gateway rejects chroma.search call attributed to campaign-agent-v1 (not in allowed_tools) → 403
AC-7: agent_decision_log receives row after admissions agent /chat request
AC-8: seed_manifests.py exits 0 on idempotent re-run (no duplicate manifests created)
AC-9: P2-GATE-02 sensor passes: registry returns 6 manifests; decision log receiving entries
AC-10: All YAML manifests committed to platform/agent-registry/manifests/ under version control
```

---

*Author: Bob (IBM Bob AI software engineer) | i3 AI Platform | 2026-09-22*  
*Do not implement until this ADR is reviewed and status changed to **Accepted** by Deciders.*
