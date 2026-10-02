"""
i3 Agentic AI OS — LangGraph Agent State Schema
File: platform/agentic-os/state.py

Defines the typed state that flows through all nodes in the ReAct graph.
Shared by agent_runtime.py and any sub-agent graphs.

HC-3: autonomy_tier stored in state; checked before any Tier 3 tool call.
HC-4: tenant_id carried in state for the full session lifetime.
HC-5: pending_approval_id stored between interrupt_before pause and resume.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Typed state for the i3 ReAct agent loop.

    LangGraph's ``add_messages`` reducer appends to the messages list on
    each node update rather than overwriting it, preserving full turn history.
    """

    # ── Identity ──────────────────────────────────────────────────────────
    agent_id:       str                         # e.g. "agentic-os-supervisor"
    tenant_id:      str                         # HC-4: UUID; sourced from Keycloak JWT
    session_id:     str                         # unique per conversation turn
    autonomy_tier:  Literal["L0", "L1"]         # HC-3: ceiling enforced at runtime

    # ── Conversation ──────────────────────────────────────────────────────
    # add_messages reducer: appends new messages rather than replacing list
    messages: Annotated[list[dict[str, Any]], add_messages]

    # ── ReAct loop control ────────────────────────────────────────────────
    # Set by the tool_call node with the tool name about to be invoked;
    # cleared after dispatch.
    pending_tool_name:  str | None

    # Set by the tool_call node with the validated input payload;
    # cleared after dispatch.
    pending_tool_input: dict[str, Any] | None

    # ── Tier 3 approval gate (HC-5) ───────────────────────────────────────
    # When the MCP Gateway returns HTTP 202, the approval_id is stored here
    # and the graph suspends at interrupt_before=["tool_call"].
    # On resume, this ID is injected back into the tool input.
    pending_approval_id: str | None

    # ── Model routing ─────────────────────────────────────────────────────
    # Set by the supervisor node to steer LiteLLM to the correct backend.
    # Values: "ibm-granite-3b-instruct" | "llama-3.3-70b-instruct" | "qwen-2.5-72b-instruct"
    selected_model: str

    # ── Token accounting ──────────────────────────────────────────────────
    total_input_tokens:  int
    total_output_tokens: int
    cost_budget_tokens:  int   # copied from agent manifest at session start

    # ── Observability ─────────────────────────────────────────────────────
    # Langfuse trace_id for the current session (set once at graph entry).
    langfuse_trace_id: str | None

    # ── Output ────────────────────────────────────────────────────────────
    final_response: str | None
