# ADR-003: MCP Tool Gateway

**Status:** Accepted  
**Date:** 2025-07-15  
**Author:** i3 Technologies Platform Team  
**Step Reference:** STEP-P2-04 (i3-platform-atomic-execution-plan.md)  
**Replaces:** No prior decision record; tool invocations were made directly from agents.

---

## Context

Prior to STEP-P2-04, the i3 platform had three AI agents — the Nuru Admissions Assistant,
the Dawa PMaaS Campaign Agent, and the Onboarding Planner — each making tool calls directly
to external services:

| Agent | Direct dependency |
|---|---|
| `admissions_agent.py` | `chromadb.HttpClient` + `llama_index` (RAG), Odoo XML-RPC, Google Calendar API, n8n webhooks |
| `campaign_agent.py` | `chromadb.HttpClient` + `chromadb.config.Settings` (RAG), LiteLLM HTTP |
| `mcp_connectors.py` | Odoo XML-RPC, Google Calendar API, n8n webhooks, Directus REST API |

This direct-call architecture violated several platform constraints:

1. **HC-5 violation.** Agents were executing state-modifying side effects (CRM writes, calendar
   bookings) without any policy gate. "Agents propose, policy disposes" was expressed only in
   documentation, not enforced at runtime.

2. **No allowed_tools enforcement.** Agent manifests in `platform/agent-registry/manifests/`
   declared `allowed_tools` and `forbidden_tools`, but no system checked whether a running agent
   respected these boundaries. Any code change could silently violate the manifest.

3. **No per-tool rate limiting.** Tier 2 (customer-facing) and Tier 3 (financial/PII write) tools
   could be called without any frequency constraint, creating both cost and safety risks.

4. **No unified audit trail.** Each agent wrote its own decision log, but individual tool
   invocations — including the external Odoo/Calendar writes — were invisible to the audit
   pipeline. There was no way to answer: "which agent called `calendar.book` at 14:37 UTC?"

5. **Tight coupling to third-party SDKs.** `chromadb`, `llama_index`, and `google-api-python-client`
   were imported in agent process images. Any ChromaDB API change or credential rotation
   required redeployment of the agent — not just the connector layer.

---

## Decision

### 1. Introduce a dedicated `mcp-gateway` FastAPI service in namespace `i3-agent-mesh`

The gateway owns a single HTTP route:

```
POST /tools/{tool_name}/invoke
  Headers: X-Agent-Id, X-Tenant-Id, X-Correlation-Id
  Body:    { input: <tool-specific payload> }
  → 200  { output, invocation_id, duration_ms }
  → 403  { error: "tool not in agent allowed_tools" }
  → 429  { error: "rate limit exceeded" }
```

All tool logic lives in `platform/mcp-gateway/tools/` as independently registered modules.
Each module calls `register_tool(McpToolSpec, handler)` at import time, making the catalogue
fully introspectable at runtime via `GET /tools`.

### 2. Define six risk tiers across all tools

| Tool | Risk Tier | Rationale |
|---|---|---|
| `chroma.search` | 0 (read-only) | No external write; idempotent |
| `odoo.crm.read` | 0 (read-only) | Read-only CRM lookup |
| `litellm.chat` | 1 (low-risk) | Cost-budgeted; no external write |
| `calendar.book` | 2 (customer-facing) | External calendar write |
| `odoo.crm.create` | 2 (customer-facing) | CRM write |
| `n8n.enrolment.trigger` | 2 (customer-facing) | Triggers external workflow |
| `directus.tasks.write` | 2 (customer-facing) | CMS write |
| `postgres.members.write` | 3 (PII/legal) | PII write — maximum restriction |

Tier 2+ tools are gated by the existing Human-in-the-Loop two-stage confirmation pattern
(stage 1 returns a Redis-backed token; stage 2 executes only after explicit human approval).

### 3. Enforce `allowed_tools` from agent manifests at runtime

Every invocation fetches the calling agent's manifest from the Agent Registry
(`GET /agents/{agent_id}`) and checks that `tool_name` is in `allowed_tools`. Manifests are
cached for 60 seconds to avoid round-trip latency on every call. The check occurs before any
rate-limit check and before the tool handler is dispatched.

A 403 response is returned (and audited) if the tool is not in the manifest. Forbidden tools
(`forbidden_tools`) are implicitly covered — any tool not listed in `allowed_tools` is blocked.

### 4. Rate-limit per tool per tenant per agent using Redis sliding window

Each tool declares a `rate_limit` (requests per minute). The gateway uses a Redis INCR+EXPIRE
pipeline on the key `mcp:rl:{tool_name}:{tenant_id}:{agent_id}`. If the count exceeds the
limit, a 429 is returned. Rate-limit failures fail-open if Redis is unavailable, to prevent
the gateway from becoming a single point of failure for read-only tools.

### 5. Write every invocation to `mcp_invocation_log` with `tenant_id NOT NULL` (HC-4)

Every invocation — including blocked and error outcomes — produces a row in
`mcp_invocation_log`. The table carries `tenant_id UUID NOT NULL` and an RLS policy. This
provides a complete, queryable audit trail for compliance, cost attribution, and incident replay.

### 6. Remove all direct SDK calls from agents

`admissions_agent.py`: removed `chromadb`, `llama_index.core`, `llama_index.vector_stores.chroma`
imports and the `_chroma_client`, `_collection`, `_vector_store`, `_index`, `_retriever`
module-level objects. `retrieve_context()` now calls `mcp_gateway_invoke("chroma.search", ...)`.

`campaign_agent.py`: removed `import chromadb` and `from chromadb.config import Settings`.
`retrieve_context()` and `llm_chat()` now call the gateway. The agent no longer holds a
`chromadb.HttpClient` instance.

`mcp_connectors.py`: refactored from a direct-implementation service (Odoo XML-RPC, Google
Calendar, Redis pending store) to a thin HTTP proxy that forwards to the gateway. All business
logic has migrated to `platform/mcp-gateway/tools/`. The original HTTP endpoint paths are
preserved for backward compatibility with any callers (e.g., onboarding-agent frontend).

---

## Consequences

### Positive

- **HC-5 compliance**: all state-modifying tool calls now pass through a policy gate with
  `allowed_tools` enforcement. No agent can call a tool outside its manifest.
- **HC-4 compliance**: every invocation carries `tenant_id` in the audit log.
- **Unified audit trail**: `mcp_invocation_log` provides a single table for "which agent called
  which tool for which tenant at what time with what outcome" queries.
- **Rate limiting**: Tier 2/3 tools are now rate-limited per tenant per agent, protecting
  external services and the platform from runaway agent loops.
- **Decoupled deployments**: ChromaDB, Odoo, and Google Calendar credential rotation only
  requires a gateway pod restart, not a redeployment of admissions-agent or campaign-agent.
- **Sensor check SC-P2-04-b** is now enforceable: `postgres.members.write` is not in
  `admissions-agent-v1.allowed_tools` and will return 403.
- **Sensor check SC-P2-04-d** passes: zero `chromadb.` or `chroma_client.` references remain
  in `admissions_agent.py`.

### Negative / Trade-offs

- **Additional network hop**: every tool call now traverses `agent → gateway → backend`.
  Expected p99 overhead is < 5 ms for intra-cluster calls.
- **Gateway is a new failure domain**: if the MCP Gateway pod is unavailable, tool calls fail.
  Mitigated by 2 replicas, readiness probes, and the 60-second manifest cache (which allows
  continued operation during brief registry outages).
- **Manifest cache staleness**: a newly revoked tool permission may take up to 60 seconds to
  propagate. This is acceptable for L0/L1 agents; L2+ agents are not deployed.
- **litellm.chat via gateway**: `campaign_agent.py` previously called LiteLLM directly. It now
  routes through the gateway, which adds one hop but centralises LiteLLM auth and rate-limits.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Enforce `allowed_tools` in each agent via decorator | No centralised audit; each agent would need its own enforcement logic; bypassed by future direct calls |
| Sidecar proxy per agent pod | More complex deployment; harder to share Redis rate-limit counters across agents |
| Kong API Gateway for tool routing | Overkill for internal cluster tool dispatch; Kong is reserved for external API boundary (STEP-P2-07) |
| Kafka-based tool dispatch | Adds Kafka dependency to all tool calls; fire-and-forget semantics incompatible with synchronous tool results |

---

## Compliance Mapping

| Requirement | Reference |
|---|---|
| HC-5 (Hard Constraint) | Agents propose, policy disposes. The MCP gateway is the policy enforcement point: no agent may invoke a tool outside its `allowed_tools` manifest. |
| HC-4 (Hard Constraint) | Every tool invocation carries `X-Tenant-Id`; the gateway rejects mismatched tenant headers (HTTP 403). |
| HC-3 (Hard Constraint) | Risk tier 3 tools (financial/legal) require explicit human approval before the gateway will process the invocation — enforced in `main.py` `invoke` endpoint. |
| Enhancement 3 Guide — E³ Principle P5 | Least-privilege tooling: each agent is constrained to the minimum required tool set declared in its manifest. |
| i3-platform-atomic-execution-plan.md | STEP-P2-04 |

---

## Sensor Checks (from STEP-P2-04)

| Check ID | Command | Expected |
|---|---|---|
| SC-P2-04-b | `curl -s -X POST http://mcp-gateway.i3-agent-mesh.svc/tools/postgres.members.write/invoke -H "X-Agent-Id: admissions-agent-v1" -d '{"input": {"test": true}}'` | HTTP 403, `"tool not in agent allowed_tools"` |
| SC-P2-04-c | `grep -n "mcp.gateway\|mcp_gateway\|MCPGATEWAY\|MCP_GATEWAY" platform/admissions/admissions_agent.py` | ≥ 1 match |
| SC-P2-04-d | `grep -n "chromadb\.\|chroma_client\." platform/admissions/admissions_agent.py` | 0 matches |

---

## Related Documents

- `i3-platform-atomic-execution-plan.md` — STEP-P2-04
- `platform/mcp-gateway/migrations/001_init.sql` — DDL
- `platform/mcp-gateway/tools/` — tool implementations
- `platform/agent-registry/manifests/` — canonical agent manifests (updated)
- `ADR-002-agent-registry-decision-log.md` — prerequisite (STEP-P2-03)
- Hard Constraints: HC-4, HC-5 (`.bob/workspace-rules/01-hard-constraints.md`)
