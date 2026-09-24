# ADR-003: MCP Tool Gateway

**Status:** Accepted  
**Date:** 2026-09-22  
**Deciders:** Agent Mesh Lead, Platform Security Lead, Engineering Manager  

---

## Context

AI agents currently call external integrations directly: ChromaDB queries inline in
`admissions_agent.py`, Kafka produces inline in `campaign_agent.py`, Odoo CRM calls via
`mcp_connectors.py` with no rate-limiting or audit.  This violates HC-5 (agents propose, policy
disposes) because there is no policy check between an agent deciding to act and the action
executing.  Tool invocations are also unauditable — there is no log of which agent called which
tool with what input.

Enhancement 3 Agentic AI Platform guide §7 and PMC guide §7.1 mandate an MCP Tool Gateway as the
single policy enforcement point for all agent tool calls.

---

## Decision

Create an `mcp-gateway` FastAPI service in the `i3-agent-mesh` namespace.  
Every registered tool MUST declare `risk_tier`, `side_effect_class`, `requires_human_gate`, and
`tenant_scoped` (mode rule requirement).  Agents MUST NOT call ChromaDB, Kafka, PostgreSQL, or
external APIs directly — all calls route through `POST /tools/{name}/invoke`.  
The gateway validates the calling agent's `allowed_tools` list against the Agent Registry before
executing any invocation.

Risk tier semantics:
- `Tier 0` — read-only (chroma.search) — no gate
- `Tier 1` — low-risk compute (litellm.chat) — rate-limit only
- `Tier 2` — customer-facing external (kafka.produce, calendar.book, odoo.crm.create) — policy check
- `Tier 3` — PII write (postgres.members.write) — human gate required

---

## Alternatives Considered

| Option | Rejected reason |
|--------|----------------|
| Per-agent tool wrappers (no central gateway) | Duplicated policy logic; audit is fragmented |
| LangGraph tool nodes | Framework lock-in; doesn't enforce cross-agent policy; no HC-5 enforcement |
| IBM API Connect as tool gateway | Cost; YAML-heavy configuration for non-HTTP tools (Kafka, ChromaDB) |

---

## Consequences

**Positive:**
- HC-5 is mechanically enforced — no agent can execute a side-effecting action without the
  gateway authorising it.
- All tool invocations are logged with `agent_id`, `tool_name`, `input_hash`, `risk_tier`,
  `duration_ms` — full audit trail.
- Credentials for external services (ChromaDB token, Kafka SASL, Odoo API key) are held only by
  the gateway, never exposed to agents.

**Negative:**
- Adds one network hop per tool call; mitigated by co-located deployment in `i3-agent-mesh`
  (< 2 ms cluster-internal latency).
- Migration adapter required during Phase 2 transition; existing direct calls are wrapped before
  they are removed.

---

## Compliance Mapping

| Constraint | How this ADR satisfies it |
|-----------|--------------------------|
| HC-3 | Gateway checks agent autonomy_level before executing Tier 2+ tools |
| HC-4 | `X-Tenant-Id` header required on every invocation; gateway injects `tenant_id` into all downstream calls |
| HC-5 | Gateway is the single policy enforcement point — agents cannot bypass it via direct calls (NetworkPolicy blocks direct access) |
| HC-6 | Gateway validates that no raw NID or phone number appears in Tier 3 tool inputs |
| E³ P3 | Agents propose (call gateway) → policy disposes (gateway authorises or rejects) |
| E³ P9 | Small surface, deep contracts — one endpoint per tool, strict Pydantic input schema |

---

## Sensor Gate (P2-GATE-03)

```bash
kubectl get pod -n i3-agent-mesh -l app=mcp-gateway   # Running
# Tool not in allowed_tools → 403
curl -s -X POST http://mcp-gateway.i3-agent-mesh.svc/tools/postgres.members.write/invoke \
  -H "X-Agent-Id: admissions-agent-v1" -d '{"input":{"test":true}}'
# Expected: 403
# Direct chromadb calls removed from agents
grep -n "chromadb\.\|chroma_client\." platform/admissions/admissions_agent.py
# Expected: 0 matches
```
