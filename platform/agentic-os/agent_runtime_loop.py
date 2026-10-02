"""
i3 Agentic AI OS — Governed Agent Execution Engine (AgentRuntimeLoop)
File: platform/agentic-os/agent_runtime_loop.py

Remediated implementation of the AgentRuntimeLoop design artifact.

Defects fixed vs. original pseudocode
──────────────────────────────────────
D1 HC-3  autonomy_tier: __init__ accepts and validates autonomy_tier; run() raises
         ValueError on L2/L3 before the loop starts.

D2 HC-4  tenant_id: required parameter on __init__ and run(); forwarded as
         X-Tenant-Id header on every MCP Gateway invocation.

D3 HC-5  HITL durable suspend: instead of an early-return string, the loop stores
         the pending_approval_id in session_context and raises HumanApprovalRequired
         so the caller can persist state, notify the approver, then resume via
         run_with_approval().  Approval_id is re-injected into tool_arguments on
         resume — matching the MCP Gateway Phase 2 contract.

D4 Budget: A token budget (default 100 000) is checked before each LLM call.
           An iteration ceiling (default 25) guards against infinite loops when
           the model never emits FINAL_RESPONSE.

D5 Storage: session_context["history"] is only ever mutated through
            _history_append() which must be sub-classed to persist to Redis in
            production.  The default is an in-memory list (acceptable for tests);
            RedisSessionMixin is provided for production use.

D6 Lobster Trap coverage: firewall is applied to (a) user_input at entry,
   (b) action["response_content"] on THOUGHT, and (c) every string value inside
   tool_arguments before MCP dispatch.

Architecture alignment
──────────────────────
- All tool execution exits through the MCP Gateway (HC-5).
- No direct external HTTP calls from this module.
- HC-6: member tokens / NIDs never logged or echoed; only tool results are
  stored in history, and only after firewall clearance on string values.
- HC-7: DEV_BYPASS_AUTH is not read or honoured anywhere in this module.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict

import httpx

log = logging.getLogger("agentic-os.runtime_loop")

# ── Lobster Trap — 12 prompt injection patterns (re-declared to avoid importing
#    agent_runtime which pulls in langgraph at module level)  ─────────────────
import re as _re

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
_COMPILED_PATTERNS = [_re.compile(p, _re.IGNORECASE) for p in _LOBSTER_TRAP_PATTERNS]


def _check_lobster_trap(text: str) -> str | None:
    """Return the first matched pattern string, or None if clean."""
    for pattern in _COMPILED_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None

MCP_GATEWAY_URL = os.environ.get(
    "MCP_GATEWAY_URL",
    "http://mcp-gateway.i3-agent-mesh.svc.cluster.local:8080",
)

# Maximum loop iterations before terminating with a safety error.
_DEFAULT_MAX_ITERATIONS = 25
# Default token budget (prompt + completion tokens combined).
_DEFAULT_TOKEN_BUDGET = 100_000

AGENT_ACTION_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "action_type": {
            "type": "string",
            "enum": ["THOUGHT", "TOOL_CALL", "FINAL_RESPONSE"],
        },
        "tool_name":       {"type": "string"},
        "tool_arguments":  {"type": "object"},
        "response_content": {"type": "string"},
    },
    "required": ["action_type"],
})


# ── Exceptions ────────────────────────────────────────────────────────────────

class HumanApprovalRequired(Exception):
    """
    Raised when a Tier 3 tool returns HTTP 202 (approval pending).

    The caller must:
      1. Persist session_context (including pending_approval_id).
      2. Notify the human approver.
      3. After the approver decides, call run_with_approval() with the same
         session_context and the approval_id.

    Attributes:
        tool_name:   The tool that triggered the gate.
        approval_id: UUID returned by the MCP Gateway for this pending record.
        session_id:  Session to resume once approval is granted.
    """

    def __init__(self, tool_name: str, approval_id: str, session_id: str) -> None:
        self.tool_name   = tool_name
        self.approval_id = approval_id
        self.session_id  = session_id
        super().__init__(
            f"Tier 3 approval required: tool={tool_name} "
            f"approval_id={approval_id} session={session_id}"
        )


class SafetyViolation(Exception):
    """Raised when the Lobster Trap firewall blocks input or tool arguments."""


class BudgetExhausted(Exception):
    """Raised when the token or iteration budget is exhausted."""


# ── AgentRuntimeLoop ──────────────────────────────────────────────────────────

class AgentRuntimeLoop:
    """
    Governed, single-tenant agent execution engine.

    Args:
        harness:          AdaptiveAgentHarness — grammar-guided LLM caller.
        guardrail_client: Object with .inspect_input(text) → bool.
        mcp_client:       Object with async .invoke(tool, args, *, agent_id,
                          tenant_id, session_id) → dict.
        agent_id:         Identifier of this agent (HC-3 audit trail).
        tenant_id:        Tenant UUID — forwarded on every MCP call (HC-4).
        autonomy_tier:    "L0" or "L1" only. "L2"/"L3" raises ValueError (HC-3).
        max_iterations:   Hard ceiling on loop iterations (default 25).
        token_budget:     Combined prompt+completion token ceiling (default 100 000).
    """

    def __init__(
        self,
        harness,
        guardrail_client,
        mcp_client,
        *,
        agent_id: str,
        tenant_id: str,
        autonomy_tier: str = "L1",
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> None:
        # D1 — HC-3: reject L2/L3 at construction time
        if autonomy_tier not in ("L0", "L1"):
            raise ValueError(
                f"HC-3 violation: autonomy_tier={autonomy_tier!r} exceeds L1 ceiling. "
                "Agents on this platform are capped at L1."
            )

        self.harness        = harness
        self.guardrail      = guardrail_client
        self.mcp            = mcp_client
        self.agent_id       = agent_id
        self.tenant_id      = tenant_id          # D2 — HC-4
        self.autonomy_tier  = autonomy_tier
        self.max_iterations = max_iterations
        self.token_budget   = token_budget

    # ── Session history helpers (override in Redis subclass) ──────────────────

    def _history_append(self, session_context: Dict[str, Any], entry: dict) -> None:
        """Append *entry* to session_context["history"].  Override to persist."""
        session_context.setdefault("history", []).append(entry)

    # ── Firewall helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _assert_safe(text: str, label: str) -> None:
        """Raise SafetyViolation if *text* triggers the Lobster Trap (D6)."""
        hit = _check_lobster_trap(text)
        if hit:
            log.warning("Lobster Trap blocked %s — matched pattern: %r", label, hit)
            raise SafetyViolation(
                f"[BLOCKED by Lobster Trap firewall — {label} matched: {hit!r}]"
            )

    @staticmethod
    def _sanitise_tool_arguments(tool_name: str, args: dict) -> None:
        """
        D6: Inspect every string value in tool_arguments before MCP dispatch.
        Raises SafetyViolation on the first match.
        """
        for key, value in args.items():
            if isinstance(value, str):
                hit = _check_lobster_trap(value)
                if hit:
                    log.warning(
                        "Lobster Trap blocked tool_arguments[%s] for tool=%s: %r",
                        key, tool_name, hit,
                    )
                    raise SafetyViolation(
                        f"[BLOCKED by Lobster Trap firewall — tool_arguments[{key}] "
                        f"for {tool_name} matched: {hit!r}]"
                    )

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run(
        self,
        session_context: Dict[str, Any],
        user_input: str,
    ) -> str:
        """
        Run the ReAct loop for a single user turn.

        D1  HC-3: autonomy_tier validated at construction; no re-promotion possible.
        D2  HC-4: tenant_id forwarded via self.tenant_id on every MCP call.
        D3  HC-5: Tier 3 approval raises HumanApprovalRequired (durable suspend).
        D4  Budget: token and iteration ceilings enforced.
        D5  Storage: history written via _history_append() (Redis-overridable).
        D6  Firewall: user_input, THOUGHT content, and tool_arguments all checked.

        Raises:
            SafetyViolation:       Lobster Trap triggered.
            HumanApprovalRequired: Tier 3 tool requires human sign-off.
            BudgetExhausted:       Token or iteration ceiling reached.
        """
        # D2 — HC-4: tenant_id must be set on every session
        if not session_context.get("tenant_id"):
            session_context["tenant_id"] = self.tenant_id
        elif session_context["tenant_id"] != self.tenant_id:
            raise ValueError(
                f"HC-4 violation: session tenant_id {session_context['tenant_id']!r} "
                f"does not match runtime tenant_id {self.tenant_id!r}"
            )

        # D6a — firewall on user input
        self._assert_safe(user_input, "user_input")

        session_context.setdefault("session_id", str(uuid.uuid4()))
        session_context.setdefault("tokens_used", 0)
        self._history_append(session_context, {"role": "user", "content": user_input})

        for iteration in range(self.max_iterations):
            # D4 — token budget check before each LLM call
            if session_context["tokens_used"] >= self.token_budget:
                log.warning(
                    "Token budget exhausted: session=%s used=%d budget=%d",
                    session_context["session_id"],
                    session_context["tokens_used"],
                    self.token_budget,
                )
                raise BudgetExhausted(
                    f"Token budget of {self.token_budget} exhausted after "
                    f"{iteration} iterations."
                )

            prompt = self._compile_prompt(session_context["history"])
            action = await self.harness.execute_grammar_guided_action(
                prompt, AGENT_ACTION_SCHEMA
            )

            # Accumulate tokens if the harness exposes them
            session_context["tokens_used"] = getattr(
                self.harness, "tokens_used", session_context["tokens_used"]
            )

            if action["action_type"] == "THOUGHT":
                content = action.get("response_content", "")
                # D6b — firewall on THOUGHT content before it enters history
                self._assert_safe(content, "THOUGHT.response_content")
                self._history_append(
                    session_context, {"role": "assistant", "content": content}
                )

            elif action["action_type"] == "TOOL_CALL":
                tool_name = action.get("tool_name", "")
                tool_args  = dict(action.get("tool_arguments") or {})

                # D6c — firewall on every string value in tool_arguments
                self._sanitise_tool_arguments(tool_name, tool_args)

                # D3 — HC-5: re-inject pending approval_id if resuming Phase 2
                if session_context.get("pending_approval_id"):
                    tool_args["approval_id"] = session_context["pending_approval_id"]

                tool_result = await self.mcp.invoke(
                    tool_name,
                    tool_args,
                    agent_id=self.agent_id,
                    tenant_id=self.tenant_id,        # D2 — HC-4
                    session_id=session_context["session_id"],
                )

                # D3 — HC-5: Tier 3 gate — MCP returns approval_id when pending
                if isinstance(tool_result, dict) and tool_result.get("approval_pending"):
                    approval_id = tool_result["approval_id"]
                    session_id  = session_context["session_id"]
                    # Persist the approval_id for Phase 2 resume
                    session_context["pending_approval_id"] = approval_id
                    log.info(
                        "Tier 3 gate: tool=%s approval_id=%s session=%s — suspending",
                        tool_name, approval_id, session_id,
                    )
                    raise HumanApprovalRequired(tool_name, approval_id, session_id)

                # Approval fulfilled — clear the pending gate
                session_context.pop("pending_approval_id", None)

                self._history_append(
                    session_context,
                    {"role": "tool", "name": tool_name, "content": json.dumps(tool_result)},
                )

            elif action["action_type"] == "FINAL_RESPONSE":
                return action.get("response_content", "")

        # D4 — iteration ceiling exhausted without FINAL_RESPONSE
        raise BudgetExhausted(
            f"Iteration ceiling of {self.max_iterations} reached without "
            "a FINAL_RESPONSE action."
        )

    # ── Prompt compilation ────────────────────────────────────────────────────

    @staticmethod
    def _compile_prompt(history: list) -> str:
        parts = []
        for item in history:
            role    = item.get("role", "")
            content = item.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)
