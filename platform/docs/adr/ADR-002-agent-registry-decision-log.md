# ADR-002: Agent Registry and Decision Log

**Status:** Accepted  
**Date:** 2025-07-14  
**Author:** i3 Technologies Platform Team  
**Step Reference:** STEP-P2-03 (i3-platform-atomic-execution-plan.md)  
**Replaces:** No prior decision record; decision logging was absent from all agents

---

## Context

Prior to Phase 2, the i3 platform operated three production AI agents — the Nuru Admissions
Assistant, the Dawa PMaaS Campaign Agent, and the Onboarding Planner — with no centralised
registry, no structured lifecycle state management, and no decision audit trail. The following
deficiencies were identified:

1. **No agent inventory.** There was no authoritative list of deployed agents, their allowed
   tools, cost budgets, or owner metadata. Evaluating the platform's AI surface area required
   reading source code.

2. **No autonomy guardrail enforcement.** Hard Constraint HC-3 (no agent autonomy above L1)
   was expressed only in documentation. There was no runtime gate blocking L2/L3 manifest
   registration.

3. **No decision traceability.** After an LLM call completed, there was no persistent record of
   which agent called which model, how many tokens were consumed, what the policy decision was,
   or which tenant the call was on behalf of. This violates Hard Constraint HC-4 (tenant_id on
   every log line) and prevents cost attribution, incident replay, and compliance audits.

4. **No structured cost accounting.** Token usage was visible only in LiteLLM proxy logs, not
   correlated with agent identity or tenant.

---

## Decision

### 1. Introduce a dedicated `agent-registry` FastAPI service in namespace `i3-agent-mesh`

The service owns two tables in a dedicated PostgreSQL database:

| Table | Purpose |
|---|---|
| `agent_registry` | Canonical manifest store — one row per deployed agent |
| `agent_decision_log` | Immutable append-only audit log — one row per LLM completion |

Both tables carry `tenant_id UUID NOT NULL` and Row-Level Security policies (HC-4).
The `agent_registry` table enforces an `autonomy_tier IN ('L0','L1')` CHECK constraint
that directly encodes HC-3. Any attempt to register an agent with `autonomy_tier = 'L2'`
or higher is rejected at the database level, not merely by application logic.

### 2. Codify each agent as a YAML manifest committed to version control

Every agent has a file in `platform/agent-registry/manifests/<agent_id>.yaml`. The manifest
declares `allowed_tools`, `forbidden_tools`, `cost_budget_tokens`, and `autonomy_tier`. This
makes the agent surface area auditable via git blame and PR review before any deployment.

At service startup, `main.py` seeds these manifests into the database with `ON CONFLICT DO
UPDATE`, so the DB always reflects the git HEAD state after every rollout.

### 3. All agents emit a fire-and-forget decision log entry after every LLM call

The emission pattern is identical across Python and TypeScript agents:

```python
# Python (admissions, campaign)
await asyncio.get_event_loop().run_in_executor(None, emit_decision, ...)
```

```typescript
// TypeScript (onboarding planner, base-scan)
emitDecision({ agentId, sessionId, model, inputTokens, outputTokens, ... });
```

The call is **non-blocking and non-retried**. If the agent registry is temporarily unavailable,
the decision record is silently dropped at debug log level. Agent functionality is unaffected.
This design satisfies the HC-5 principle (agents propose, policy disposes) — the log is
observability infrastructure, not a gate that can hold up real-time agent responses.

---

## Consequences

### Positive

- **HC-3 compliance** is enforced at the database and application levels, not only by convention.
- **HC-4 compliance**: every decision record carries `tenant_id`.
- **Cost attribution**: `input_tokens`, `output_tokens`, and `cost_usd` per tenant per agent
  per session are queryable from a single table.
- **Incident replay**: `correlation_id` and `session_id` fields allow full reconstruction of an
  agent session from the decision log.
- **Audit trail for governance**: policy decision (`allowed` | `blocked` | `escalated`) and
  `human_approver` fields provide the data model for future L2-promotion review evidence.
- **MCP gateway prerequisite**: STEP-P2-04 (MCP Tool Gateway) depends on the registry to
  validate `allowed_tools` — the manifest schema established here is the contract it will consume.

### Negative / Trade-offs

- **Additional service to operate**: the registry is a new pod in `i3-agent-mesh`. It must be
  healthy for manifest seeding to succeed on startup.
- **Eventual consistency on startup**: if the registry pod restarts before agents, agents will
  silently drop decision records until it recovers. This is acceptable — decisions are
  observability, not transactional.
- **Approximate token counts**: Python agents approximate token usage by word-count (LiteLLM
  streaming responses do not return `usage` in the streaming path). TypeScript agents use the
  `completion.usage` object from the OpenAI SDK (accurate when available).

---

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Store manifests only in YAML, no DB | No runtime enforcement of HC-3; no queryable inventory API |
| Emit decisions to Kafka topic | Adds Kafka dependency to Python agents; fire-and-forget HTTP is simpler and sufficient for L0/L1 |
| Block agent responses if registry is down | Violates availability requirement — observability must never gate functionality at this tier |
| One shared decision-log table per service | Violates single-source-of-truth; cross-agent queries require joins across service DBs |

---

## Compliance Mapping

| Requirement | Reference |
|---|---|
| HC-3 (Hard Constraint) | All agent manifests are gated at L0/L1 autonomy. The registry enforces this on seed and rejects any PATCH that would promote a manifest above L1. |
| HC-4 (Hard Constraint) | `agent_decision_log` carries `tenant_id UUID NOT NULL`; RLS isolates decision records by tenant. |
| HC-5 (Hard Constraint) | Decision log records every tool invocation and `policy_decision` outcome, providing the audit trail that HC-5 requires before any state-modifying action. |
| Enhancement 3 Guide — E³ Principle P11 | Explainability: the decision log makes every agent action traceable to a session, model, and approval outcome. |
| i3-platform-atomic-execution-plan.md | STEP-P2-03 |

---

## Sensor Checks (from STEP-P2-03)

| Check ID | Command | Expected |
|---|---|---|
| SC-P2-03-b | `curl -s http://agent-registry.i3-agent-mesh.svc/agents \| python3 -c "import sys,json; print(len(json.load(sys.stdin)['agents']))"` | ≥ 3 |
| SC-P2-03-c | `SELECT count(*) FROM agent_decision_log WHERE agent_id = 'admissions-agent-v1'` | > 0 after one /chat request |
| SC-P2-03-d | `python3 -c "import yaml,glob; [(__import__('builtins').setattr(__import__('builtins'), '_', m) or None) for f in glob.glob('/app/manifests/*.yaml') for m in [yaml.safe_load(open(f))]] ; [print('OK') if m['autonomy_tier'] in ('L0','L1') else (_ for _ in ()).throw(AssertionError(f)) for f in glob.glob('/app/manifests/*.yaml') for m in [yaml.safe_load(open(f))]]"` | OK for all manifests |

---

## Related Documents

- `i3-platform-atomic-execution-plan.md` — STEP-P2-03
- `platform/agent-registry/migrations/001_init.sql` — DDL
- `platform/agent-registry/manifests/` — canonical agent manifests
- `ADR-001-consent-service-extraction.md` — companion P2 decision
- Hard Constraints: HC-3, HC-4, HC-5 (`.bob/workspace-rules/01-hard-constraints.md`)
