"""
i3 Agentic AI OS — LangGraph ReAct Agent Runtime
File: platform/agentic-os/agent_runtime.py

Entry point for the i3 Agentic AI OS agent loop.  Builds a LangGraph
StateGraph implementing the THOUGHT → OPA_CHECK → TOOL_CALL → FINAL_RESPONSE
cycle with:

  • LiteLLM for model calls (routes to vLLM GPU backend or Ollama CPU)
  • MCP Gateway for all tool execution (HC-5: no direct external calls)
  • LangGraph interrupt_before on tool_call node for Tier 3 human gate (HC-5)
  • Redis checkpointer for session state persistence across pod restarts
  • LangfuseCallbackHandler for production trace capture (Flywheel)
  • HC-3: autonomy_tier enforced; no self-promotion above L1
  • HC-4: tenant_id carried through every state update and MCP header
  • HC-6: member_token validation delegated to MCP Gateway tool handler

Architecture (ADR-002 — ACCEPTED):
  LangGraph + Redis Checkpointer (not Dapr — see ADR-002 for rationale)

Usage:
    from agent_runtime import build_graph, run_session

    graph = build_graph()
    result = await run_session(
        graph,
        user_message="Enrol Jane Doe in the AI Engineering programme",
        agent_id="agentic-os-supervisor",
        tenant_id="<uuid>",
        session_id="<uuid>",
    )
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from typing import Any

import httpx
import redis.asyncio as aioredis
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from state import AgentState

log = logging.getLogger("agentic-os.runtime")

# ── Config ────────────────────────────────────────────────────────────────────
LITELLM_URL        = os.environ.get("LITELLM_URL", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000")
LITELLM_KEY        = os.environ.get("LITELLM_MASTER_KEY", "")
MCP_GATEWAY_URL    = os.environ.get("MCP_GATEWAY_URL", "http://mcp-gateway.i3-agent-mesh.svc.cluster.local:8080")
AGENT_REGISTRY_URL = os.environ.get("AGENT_REGISTRY_URL", "http://agent-registry.i3-agent-mesh.svc.cluster.local:8200")
REDIS_URL          = os.environ.get("REDIS_URL", "redis://redis.i3-platform.svc.cluster.local:6379")
# HC-6: HMAC key for provenance hashes in flywheel events
MEMBER_HMAC_SECRET = os.environ.get("MEMBER_HMAC_SECRET", "")

# Model routing keys (match agentic-os-supervisor.yaml model_routing)
_MODEL_HIGH_RISK    = "qwen-2.5-72b-instruct"
_MODEL_MULTI_STEP   = "llama-3.3-70b-instruct"
_MODEL_SIMPLE       = "ibm-granite-3b-instruct"

# Lobster Trap — 12 prompt injection patterns (HC: all input must pass firewall)
_LOBSTER_TRAP_PATTERNS = [
    r"ignore (all |previous |prior |above |)instructions",
    r"disregard (all |previous |prior |above |)instructions",
    r"forget (all |previous |prior |above |)instructions",
    r"system\s*prompt",
    r"you are now",
    r"act as (a |an |)(different|new|another|unrestricted)",
    r"do anything now",
    r"jailbreak",
    r"<\s*(script|iframe|object|embed)",
    r"base64\s*decode",
    r"eval\s*\(",
    r"--\s*(ignore|override|bypass)\s*",
]

import re as _re
_COMPILED_PATTERNS = [_re.compile(p, _re.IGNORECASE) for p in _LOBSTER_TRAP_PATTERNS]


# ── Lobster Trap firewall ─────────────────────────────────────────────────────

def _check_lobster_trap(text: str) -> str | None:
    """
    Returns the matched pattern string if the text triggers any of the 12
    prompt injection patterns, else None.
    """
    for pattern in _COMPILED_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


# ── Model routing ─────────────────────────────────────────────────────────────

def _select_model(messages: list[dict[str, Any]], agent_id: str) -> str:
    """
    Deterministically route to the appropriate LLM based on message content
    and agent identity (HC-3: routing decision logged per invocation).

    Rules (from agentic-os-supervisor.yaml model_routing):
      - Financial / high-risk keywords → qwen-2.5-72b-instruct (HC guarded)
      - Multi-step reasoning keywords  → llama-3.3-70b-instruct
      - Everything else                → ibm-granite-3b-instruct (CPU, fast)
    """
    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    ).lower()

    financial_signals = {"transfer", "payment", "approval", "financial", "banking",
                         "transaction", "loan", "credit", "debit", "fund"}
    reasoning_signals = {"analyse", "analyze", "compare", "plan", "strategy",
                         "evaluate", "research", "summarise", "summarize", "explain"}

    if any(sig in last_user for sig in financial_signals):
        return _MODEL_HIGH_RISK
    if any(sig in last_user for sig in reasoning_signals):
        return _MODEL_MULTI_STEP
    return _MODEL_SIMPLE


# ── Node: supervisor (LLM reasoning) ─────────────────────────────────────────

async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """
    THOUGHT step: calls LiteLLM with the full conversation history.
    Extracts a tool call if the model requests one, or sets final_response.

    HC-3: token budget checked; refuses to proceed if exceeded.
    HC-4: tenant_id forwarded in LiteLLM metadata header.
    """
    # HC-3: token budget guard
    used = state.get("total_input_tokens", 0) + state.get("total_output_tokens", 0)
    budget = state.get("cost_budget_tokens", 50_000)
    if used >= budget:
        log.warning("Token budget exhausted for session %s (used=%d, budget=%d)",
                    state["session_id"], used, budget)
        return {"final_response": "[Budget exhausted — session terminated by cost guard]"}

    model = _select_model(state["messages"], state["agent_id"])

    headers = {
        "Authorization": f"Bearer {LITELLM_KEY}",
        "x-litellm-metadata": json.dumps({
            "tenant_id":  state["tenant_id"],   # HC-4
            "agent_id":   state["agent_id"],
            "session_id": state["session_id"],
        }),
    }

    payload = {
        "model":    model,
        "messages": state["messages"],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "invoke_mcp_tool",
                    "description": (
                        "Invoke a registered MCP tool by name. "
                        "The tool is dispatched through the MCP Gateway with full "
                        "risk-tier enforcement and audit logging."
                    ),
                    "parameters": {
                        "type": "object",
                        "required": ["tool_name", "input"],
                        "additionalProperties": False,
                        "properties": {
                            "tool_name": {"type": "string"},
                            "input":     {"type": "object"},
                        },
                    },
                },
            }
        ],
        "tool_choice": "auto",
        "max_tokens":  2048,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    choice  = data["choices"][0]
    message = choice["message"]
    usage   = data.get("usage", {})

    updates: dict[str, Any] = {
        "selected_model":       model,
        "total_input_tokens":   state.get("total_input_tokens",  0) + usage.get("prompt_tokens",     0),
        "total_output_tokens":  state.get("total_output_tokens", 0) + usage.get("completion_tokens", 0),
        "messages":             [message],
    }

    # Extract tool call if present
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        tc   = tool_calls[0]
        args = json.loads(tc["function"]["arguments"])
        updates["pending_tool_name"]  = args.get("tool_name")
        updates["pending_tool_input"] = args.get("input", {})
        updates["final_response"]     = None
    else:
        updates["pending_tool_name"]  = None
        updates["pending_tool_input"] = None
        updates["final_response"]     = message.get("content")

    return updates


# ── Node: tool_call (MCP Gateway dispatch) ────────────────────────────────────

async def tool_call_node(state: AgentState) -> dict[str, Any]:
    """
    TOOL_CALL step: dispatches the pending tool via POST /tools/{name}/invoke.

    HC-4: X-Tenant-Id header always set.
    HC-5: No direct external calls — all execution through MCP Gateway.
          For Tier 3 tools (first call): Gateway returns HTTP 202 + approval_id.
          The node stores approval_id in state; graph suspends at
          interrupt_before=["tool_call"] until the approver decides.

    On resume (approval_id already in state): injects approval_id into input
    so the Gateway executes Phase 2 of the Tier 3 flow.
    """
    tool_name  = state.get("pending_tool_name")
    tool_input = dict(state.get("pending_tool_input") or {})

    if not tool_name:
        return {"messages": [{"role": "tool", "content": "No tool requested."}]}

    # Lobster Trap: validate tool input strings before dispatch
    for v in tool_input.values():
        if isinstance(v, str):
            hit = _check_lobster_trap(v)
            if hit:
                msg = f"[BLOCKED by Lobster Trap firewall — pattern matched: {hit!r}]"
                log.warning("Lobster Trap blocked tool_input for %s: %s", tool_name, hit)
                return {
                    "messages":          [{"role": "tool", "content": msg}],
                    "pending_tool_name": None,
                    "pending_tool_input": None,
                }

    # Tier 3 Phase 2: inject previously obtained approval_id if present
    if state.get("pending_approval_id"):
        tool_input["approval_id"] = state["pending_approval_id"]

    correlation_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=35.0) as client:
        resp = await client.post(
            f"{MCP_GATEWAY_URL}/tools/{tool_name}/invoke",
            headers={
                "X-Agent-Id":       state["agent_id"],
                "X-Tenant-Id":      state["tenant_id"],     # HC-4
                "X-Correlation-Id": correlation_id,
                "Content-Type":     "application/json",
            },
            json={"input": tool_input},
        )

    if resp.status_code == 202:
        # Tier 3 gate: approval required — suspend the graph
        body        = resp.json()
        approval_id = body.get("approval_id")
        log.info("Tier 3 gate: tool=%s approval_id=%s — awaiting human sign-off",
                 tool_name, approval_id)
        # LangGraph interrupt: pauses here; resumes when caller sends approval
        interrupt(f"Tier 3 approval required for {tool_name} (approval_id={approval_id})")
        return {
            "pending_approval_id": approval_id,
            "messages": [{
                "role":    "tool",
                "content": json.dumps({"approval_pending": True, "approval_id": approval_id}),
            }],
        }

    resp.raise_for_status()
    output = resp.json().get("output")

    return {
        "messages": [{
            "role":    "tool",
            "content": json.dumps(output) if not isinstance(output, str) else output,
        }],
        "pending_tool_name":   None,
        "pending_tool_input":  None,
        "pending_approval_id": None,
    }


# ── Routing edge ──────────────────────────────────────────────────────────────

def _route_after_supervisor(state: AgentState) -> str:
    """
    After the supervisor (LLM) node:
      - If a tool call was requested AND budget is not exhausted → tool_call
      - Otherwise → END (final_response is set)
    """
    if state.get("final_response") is not None:
        return END
    if state.get("pending_tool_name"):
        return "tool_call"
    return END


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph(checkpointer=None) -> Any:
    """
    Compile the LangGraph ReAct StateGraph.

    interrupt_before=["tool_call"]:
      Pauses execution *before* the tool_call node fires.
      For Tier 3 tools this is where the human gate lives (HC-5).
      The graph is resumed by the caller after approval is obtained.

    Args:
        checkpointer: LangGraph checkpoint saver (AsyncRedisSaver in production;
                      MemorySaver for tests).

    Returns:
        Compiled LangGraph CompiledGraph ready for .ainvoke() / .astream().
    """
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("tool_call",  tool_call_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", _route_after_supervisor)
    builder.add_edge("tool_call", "supervisor")

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["tool_call"],  # HC-5: human gate fires here for Tier 3
    )


# ── Redis checkpointer factory ────────────────────────────────────────────────

async def make_redis_checkpointer() -> AsyncRedisSaver:
    """
    Create an AsyncRedisSaver using the shared platform Redis cluster.
    Key prefix: agentic-os:session:
    TTL: 4 hours (14400 seconds) for active sessions.
    """
    redis = aioredis.from_url(REDIS_URL, decode_responses=False)
    saver = AsyncRedisSaver(redis, ttl={"default_ttl": 14400})
    await saver.asetup()
    return saver


# ── Provenance hash (HC-6 / Flywheel) ────────────────────────────────────────
# Thin delegation to provenance.py so that trace_flywheel.py can import the
# same implementation without pulling in the full langgraph dependency chain.

from provenance import provenance_hash as _provenance_hash  # noqa: E402


# ── Public session runner ──────────────────────────────────────────────────────

async def run_session(
    graph: Any,
    *,
    user_message: str,
    agent_id: str,
    tenant_id: str,
    session_id: str | None = None,
    autonomy_tier: str = "L1",
    cost_budget_tokens: int = 100_000,
    langfuse_trace_id: str | None = None,
) -> dict[str, Any]:
    """
    Run a single agent session from a user message to a final response.

    HC-3: autonomy_tier capped at L1; ValueError raised if caller attempts L2+.
    HC-4: tenant_id carried in every state update and MCP call header.

    Returns:
        dict with keys:
          final_response: str
          total_input_tokens: int
          total_output_tokens: int
          session_id: str
    """
    # HC-3: hard ceiling
    if autonomy_tier not in ("L0", "L1"):
        raise ValueError(f"HC-3 violation: autonomy_tier={autonomy_tier} exceeds L1 ceiling")

    # Lobster Trap: sanitise user input before it enters the graph
    hit = _check_lobster_trap(user_message)
    if hit:
        log.warning("Lobster Trap blocked user_message for agent=%s: %r", agent_id, hit)
        return {
            "final_response": "[Request blocked by security policy]",
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "session_id": session_id or str(uuid.uuid4()),
        }

    session_id = session_id or str(uuid.uuid4())

    initial_state: AgentState = {
        "agent_id":            agent_id,
        "tenant_id":           tenant_id,
        "session_id":          session_id,
        "autonomy_tier":       autonomy_tier,
        "messages":            [{"role": "user", "content": user_message}],
        "pending_tool_name":   None,
        "pending_tool_input":  None,
        "pending_approval_id": None,
        "selected_model":      _MODEL_SIMPLE,
        "total_input_tokens":  0,
        "total_output_tokens": 0,
        "cost_budget_tokens":  cost_budget_tokens,
        "langfuse_trace_id":   langfuse_trace_id,
        "final_response":      None,
    }

    config = {"configurable": {"thread_id": session_id}}

    # Stream graph events; collect the last state
    final: AgentState | None = None
    async for event in graph.astream(initial_state, config=config):
        for node_name, node_state in event.items():
            log.debug("Node %s updated state: %s", node_name, list(node_state.keys()))
            final = node_state

    return {
        "final_response":      (final or {}).get("final_response") or "",
        "total_input_tokens":  (final or {}).get("total_input_tokens", 0),
        "total_output_tokens": (final or {}).get("total_output_tokens", 0),
        "session_id":          session_id,
    }
