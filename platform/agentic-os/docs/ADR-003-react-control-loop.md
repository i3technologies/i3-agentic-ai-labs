# ADR-003: Resilient LangGraph ReAct Control Loop
# File: platform/agentic-os/docs/ADR-003-react-control-loop.md
#
# Status:    ACCEPTED
# Date:      2025-07-21
# Scope:     App 3 — Agentic AI OS resilient agent execution loop
# Relates:   ADR-002 (LangGraph chosen over Dapr), HC-3, HC-4, HC-5

---

## Control Loop Architecture

The i3 Agentic AI OS implements a ReAct (Reason + Act) loop as a LangGraph
`StateGraph` with Redis checkpointing.  Every state transition is durable:
if the pod restarts between nodes, Redis holds the full `AgentState` snapshot
and LangGraph replays from the last confirmed checkpoint.

### Node Map

```
  START
    │
    ▼
 ┌──────────────┐   budget_exhausted OR no tool call
 │  supervisor  │──────────────────────────────────────────► END
 │  (THOUGHT)   │
 └──────┬───────┘
        │  pending_tool_name set
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │  interrupt_before["tool_call"]   (HC-5 gate)            │
 │  LangGraph suspends graph here for Tier 3 tools.        │
 │  The graph is resumed by the approvals endpoint after   │
 │  a human signs POST /approvals/{id}/decide APPROVED.    │
 └──────┬──────────────────────────────────────────────────┘
        │
        ▼
 ┌──────────────┐   tool result appended to messages
 │  tool_call   │──────────────────────────────────────────► supervisor
 │  (TOOL_CALL) │   (loop back for next THOUGHT step)
 └──────────────┘
```

### Resilience Mechanisms

| Failure mode                | Recovery mechanism                          |
|-----------------------------|---------------------------------------------|
| Pod OOMKilled mid-loop      | Redis checkpoint → LangGraph replays from last confirmed node |
| Tool timeout (35 s)         | `asyncio.wait_for` raises TimeoutError → supervisor retry |
| Tier 3 gate pending         | `interrupt_before` suspends graph; Redis holds state indefinitely until resumed |
| Budget exhausted            | `supervisor_node` returns `final_response` → graph exits cleanly |
| Lobster Trap injection      | `_check_lobster_trap` blocks at graph entry AND at tool dispatch |
| LiteLLM backend unavailable | `httpx.AsyncClient` raises; graph emits error final_response |
| Redis unavailable           | `MemorySaver` fallback (dev/test); alert fires in prod |

### State Persistence Contract

- **Key prefix:** `agentic-os:session:{session_id}`
- **TTL:** 14 400 s (4 h) for active sessions; tunable via `REDIS_SESSION_TTL`
- **Serialisation:** LangGraph `AsyncRedisSaver` — typed AgentState pickled to Redis
- **Replay guarantee:** all message history, token counters, and pending_approval_id
  survive pod restarts and are replayed by LangGraph before node execution resumes

### Human-in-the-Loop (HITL) Escalation Path

```
agent_runtime.tool_call_node
  │  POST /tools/{name}/invoke   (no approval_id in input)
  ▼
mcp_gateway.invoke_tool
  │  risk_tier == 3 → _stage_approval() → INSERT human_approval_records(PENDING)
  ▼  HTTP 202  { approval_id }
agent_runtime.tool_call_node
  │  LangGraph interrupt("Tier 3 approval required …")
  ▼  graph SUSPENDED in Redis
  
  [Human receives notification]
  │  POST /approvals/{approval_id}/decide  { status: "APPROVED" }
  ▼
mcp_gateway.decide_approval  → UPDATE human_approval_records(APPROVED)

  [Agent or orchestrator resumes session]
  │  graph.ainvoke(None, config={"thread_id": session_id})
  ▼
agent_runtime.tool_call_node  (resumes with pending_approval_id in state)
  │  POST /tools/{name}/invoke  { approval_id: <uuid> }
  ▼
mcp_gateway._verify_approval() → executes handler → HTTP 200
```

### Financial-Threshold Escalation

Tools that carry an `estimated_value_usd` field in their input follow an
additional pre-check in the OPA policy layer **before** the MCP Gateway
dispatches to the tool handler.  The OPA rule `financial_tool_allow` in
`platform/agentic-os/policies/financial_tools.rego` enforces:

  - `estimated_value_usd` < 500 → auto-approved (Tier 2 path)
  - `estimated_value_usd` ≥ 500 → requires supervisor (Tier 3 path)

This is enforced at the MCP Gateway OPA sidecar on every tool invocation
that declares `side_effect_class = "financial"`.

### Token Budget Control Flow

```
supervisor_node entry
  │
  ├─ tokens_used = total_input_tokens + total_output_tokens
  ├─ budget = state["cost_budget_tokens"]   (from agent manifest)
  │
  ├─ tokens_used ≥ budget?
  │     YES → return final_response="[Budget exhausted]" → graph exits
  │     NO  → proceed to model routing
  │
  └─ model_router.select_model(messages, tokens_used=tokens_used, token_budget=budget)
         │
         ├─ budget_ratio ≥ 0.80 → force ibm-granite-3b-instruct
         ├─ budget_ratio ∈ [0.50, 0.80) → dampen complexity score × 0.5
         └─ budget_ratio < 0.50 → full scoring
```

## Implementation Files

| File | Role |
|------|------|
| `platform/agentic-os/agent_runtime.py` | LangGraph graph definition, nodes, checkpointer |
| `platform/agentic-os/state.py` | Typed AgentState schema |
| `platform/agentic-os/router/model_router.py` | Adaptive model routing algorithm |
| `platform/agentic-os/policies/financial_tools.rego` | OPA financial threshold policy |
| `platform/mcp-gateway/main.py` | Tier 3 gate: staging, approval, verification, audit |
| `platform/agentic-os/vllm-deploy.yaml` | GPU inference backend (Llama-70B + Qwen-72B) |
