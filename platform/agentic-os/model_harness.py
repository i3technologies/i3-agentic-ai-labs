"""
i3 Agentic AI OS — Adaptive Model Router & Harness
File: platform/agentic-os/model_harness.py

Wraps the weighted model router (router/model_router.py) with a grammar-guided
execution harness that dispatches inference requests through the platform's
LiteLLM proxy, which in turn routes to the appropriate vLLM backend:

  ┌─────────────────────────────┬───────────────────────────────────────────────┐
  │ Model                       │ Backend                                       │
  ├─────────────────────────────┼───────────────────────────────────────────────┤
  │ qwen-2.5-72b-instruct       │ vllm-qwen  svc :8001  (financial / high-risk) │
  │ llama-3.3-70b-instruct      │ vllm-inference svc :8000 (complex reasoning)  │
  │ ibm-granite-3b-instruct     │ Ollama CPU (fast / cheap)                     │
  └─────────────────────────────┴───────────────────────────────────────────────┘

Grammar-guided decoding is implemented via the vLLM OpenAI-compatible extension:
  POST /v1/chat/completions with extra_body={"guided_json": <schema>}
This is forwarded transparently by LiteLLM when the backend is a vLLM server.

HC-3: every routing decision and grammar-guided call is logged with agent_id
      and session_id for audit trail (delegated to model_router._log_decision).
HC-4: tenant_id forwarded in x-litellm-metadata header on every request.
HC-5: all LLM calls exit through the LiteLLM proxy; no direct vLLM HTTP.

Usage:
    harness = AdaptiveAgentHarness(agent_id="agentic-os-supervisor",
                                   tenant_id="<uuid>",
                                   session_id="<uuid>")

    # Route without grammar constraint
    model = harness.route_task(messages)

    # Execute with JSON-schema grammar (grammar-guided decoding)
    result = await harness.execute_grammar_guided_action(
        prompt="Extract the payment details as JSON",
        schema={"type": "object", "properties": {...}},
        messages=conversation_history,
    )
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from router.model_router import RoutingDecision, select_model

log = logging.getLogger("agentic-os.harness")

# ── Config (mirrors agent_runtime.py env vars) ────────────────────────────────
LITELLM_URL  = os.environ.get("LITELLM_URL",
               "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000")
LITELLM_KEY  = os.environ.get("LITELLM_MASTER_KEY", "")

_DEFAULT_MAX_TOKENS = 1024
_DEFAULT_TEMPERATURE = 0.0   # deterministic for grammar-guided calls


class AdaptiveAgentHarness:
    """
    Adaptive routing harness for the i3 Agentic AI OS.

    Selects the appropriate LLM via the weighted router, then dispatches
    inference through the LiteLLM proxy.  Grammar-guided decoding is
    requested via the vLLM ``guided_json`` extension (extra_body field).

    Args:
        agent_id:   Identifier of the calling agent (HC-3 audit trail).
        tenant_id:  Tenant UUID forwarded in every LiteLLM call (HC-4).
        session_id: Session UUID for routing audit log correlation.
        token_budget: Hard token ceiling for this harness instance.
        tokens_used:  Tokens already consumed in the current session.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        tenant_id: str,
        session_id: str,
        token_budget: int = 100_000,
        tokens_used: int = 0,
    ) -> None:
        self.agent_id     = agent_id
        self.tenant_id    = tenant_id
        self.session_id   = session_id
        self.token_budget = token_budget
        self.tokens_used  = tokens_used

    # ── Public: routing ───────────────────────────────────────────────────────

    def route_task(
        self,
        messages: list[dict[str, Any]],
    ) -> RoutingDecision:
        """
        Evaluate messages and return a RoutingDecision (including selected model).

        Delegates to the weighted router (score_financial / score_complexity)
        with the current token budget state.  HC-3 audit logging is emitted
        inside select_model via _log_decision.

        Returns:
            RoutingDecision — call .model to obtain the model identifier string.
        """
        return select_model(
            messages,
            agent_id=self.agent_id,
            session_id=self.session_id,
            tokens_used=self.tokens_used,
            token_budget=self.token_budget,
        )

    # ── Public: grammar-guided execution ─────────────────────────────────────

    async def execute_grammar_guided_action(
        self,
        prompt: str,
        schema: dict[str, Any] | str,
        *,
        messages: list[dict[str, Any]] | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = _DEFAULT_TEMPERATURE,
    ) -> dict[str, Any]:
        """
        Execute a grammar-guided LLM call and return parsed JSON output.

        The model is selected by routing the full conversation (or the single
        prompt wrapped as a user message when *messages* is omitted).

        Grammar enforcement is requested via the vLLM ``guided_json`` field
        passed in ``extra_body``.  LiteLLM forwards this transparently to
        vLLM backends; Ollama (Granite-3B) falls back to unguided output and
        the response is still JSON-parsed (Granite-3B is used only when task
        is simple enough that structured output is expected without guidance).

        Args:
            prompt:      The user instruction for this action.
            schema:      JSON Schema dict (or its JSON string) that constrains
                         the model's output.
            messages:    Full conversation history.  If omitted, a single-turn
                         context is constructed from *prompt*.
            max_tokens:  Token ceiling for the completion.
            temperature: Sampling temperature (0.0 for deterministic output).

        Returns:
            Parsed dict from the model's JSON response.

        Raises:
            httpx.HTTPStatusError: On non-2xx response from LiteLLM proxy.
            json.JSONDecodeError:  If the model output is not valid JSON.
        """
        if messages is None:
            messages = [{"role": "user", "content": prompt}]
        else:
            # Append prompt as the final user turn when a history is provided
            messages = list(messages) + [{"role": "user", "content": prompt}]

        decision = self.route_task(messages)
        model = decision.model

        schema_obj: dict[str, Any] = (
            json.loads(schema) if isinstance(schema, str) else schema
        )

        payload: dict[str, Any] = {
            "model":       model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            # vLLM grammar-guided decoding extension (forwarded by LiteLLM)
            "extra_body": {"guided_json": schema_obj},
        }

        headers = {
            "Authorization":    f"Bearer {LITELLM_KEY}",
            "Content-Type":     "application/json",
            "x-litellm-metadata": json.dumps({
                "tenant_id":  self.tenant_id,   # HC-4
                "agent_id":   self.agent_id,
                "session_id": self.session_id,
            }),
        }

        log.info(
            "grammar_guided_action agent=%s session=%s model=%s schema_keys=%s",
            self.agent_id, self.session_id, model,
            list(schema_obj.get("properties", {}).keys()),
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        raw_text = data["choices"][0]["message"]["content"]

        # Update consumed token count for future routing decisions
        usage = data.get("usage", {})
        self.tokens_used += (
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        )

        return json.loads(raw_text)
