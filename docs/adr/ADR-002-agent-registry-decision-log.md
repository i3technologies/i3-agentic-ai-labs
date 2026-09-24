# ADR-002: Agent Registry and Decision Log

**Status:** Accepted  
**Date:** 2026-09-22  
**Deciders:** Agent Mesh Lead, Engineering Manager  

---

## Context

All AI agents (Nuru admissions, Dawa PMaaS campaign, onboarding planner, three onboarding
subagents) operate without a shared governance plane.  There is no authoritative list of
which agents exist, what tools they may call, what their cost budgets are, or what decisions
they have made.  HC-3 requires that no agent be promoted beyond L1 autonomy without evaluation
evidence — an unenforceable requirement without a registry.

The Enhancement 3 Agentic AI Platform guide §4.1 and §14 mandate an Agent Registry and a
structured Decision Log as foundational control-plane components.

---

## Decision

Create a `agent-registry` FastAPI microservice in the `i3-agent-mesh` namespace that:
1. Stores one YAML manifest per agent (committed to `platform/agent-registry/manifests/`).
2. Enforces `autonomy_level` values — any manifest with `L2` or `L3` is rejected at POST time (HC-3).
3. Accepts fire-and-forget `POST /decisions` events from all agents after every LLM call.
4. Exposes `GET /agents/{id}/decisions` for audit.

Every agent manifest MUST declare `risk_tier`, `side_effect_class`, and `cost_budget_tokens`
(mode rule requirement).

---

## Alternatives Considered

| Option | Rejected reason |
|--------|----------------|
| Static YAML files only (no service) | No runtime enforcement of allowed_tools; no decision log |
| LangSmith / external tracing | Vendor dependency; no policy-enforcement capability; HC-4 tenancy harder |
| Embed registry in MCP Gateway | Circular dependency — gateway needs registry to validate callers |

---

## Consequences

**Positive:**
- HC-3 autonomy ceiling is machine-enforced at manifest registration, not just documentation.
- Decision log enables per-tenant cost attribution and audit evidence for HC-3 promotion reviews.
- Agent lifecycle state machine (`active → suspended → retired`) enables safe rollout control.

**Negative:**
- All agents gain a fire-and-forget HTTP call after every LLM invocation; latency impact is
  negligible (non-blocking, < 5 ms p99) but adds a network hop.
- Manifest schema must be versioned as agents evolve.

---

## Compliance Mapping

| Constraint | How this ADR satisfies it |
|-----------|--------------------------|
| HC-3 | Registry rejects any manifest with `autonomy_level: L2` or `L3` |
| HC-4 | `tenant_id UUID NOT NULL` on `agent_decision_log`; all decisions scoped to tenant |
| HC-5 | Manifests declare `allowed_tools` and `forbidden_tools`; MCP Gateway checks against registry |
| E³ P11 | Progressive autonomy — promotion from L0→L1 requires decision log evidence review |

---

## Sensor Gate (P2-GATE-02)

```bash
kubectl get pod -n i3-agent-mesh -l app=agent-registry   # Running
curl -s http://agent-registry.i3-agent-mesh.svc/agents \
  | python3 -c "import sys,json; assert len(json.load(sys.stdin)) == 6; print('OK')"
# Expected: OK
kubectl exec -n i3-agent-mesh deploy/agent-registry -- python3 -c "
import yaml, glob
for f in glob.glob('/app/manifests/*.yaml'):
    m = yaml.safe_load(open(f))
    assert m['autonomy_level'] in ('L0','L1'), f'FAIL: {f}'
print('OK')"
# Expected: OK
```
