"""
Tests — AdaptiveAgentHarness
File: platform/agentic-os/tests/test_model_harness.py

Covers:
  - route_task delegates to model_router and returns a RoutingDecision
  - route_task correctly selects model based on message content
  - tokens_used is updated after execute_grammar_guided_action
  - execute_grammar_guided_action builds correct payload (guided_json, HC-4 header)
  - execute_grammar_guided_action returns parsed JSON from model output
  - schema passed as string is decoded before forwarding
  - messages=None constructs a single-turn context from prompt
  - messages list gets prompt appended as final user turn
  - HTTPStatusError from LiteLLM propagates unmodified
  - JSONDecodeError from non-JSON model output propagates unmodified
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from model_harness import AdaptiveAgentHarness
from router.model_router import MODEL_HIGH_RISK, MODEL_MULTI_STEP, MODEL_SIMPLE


# ── Helpers ───────────────────────────────────────────────────────────────────

def _harness(**kwargs) -> AdaptiveAgentHarness:
    defaults = dict(
        agent_id="test-agent",
        tenant_id="00000000-0000-0000-0000-000000000001",
        session_id="sess-001",
    )
    defaults.update(kwargs)
    return AdaptiveAgentHarness(**defaults)


def _msg(text: str) -> list[dict]:
    return [{"role": "user", "content": text}]


def _litellm_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 20):
    """Build a minimal OpenAI-compatible chat completion response dict."""
    return {
        "choices": [{"message": {"content": content, "role": "assistant"}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


# ── route_task ────────────────────────────────────────────────────────────────

def test_route_task_returns_routing_decision():
    h = _harness()
    decision = h.route_task(_msg("hello"))
    assert hasattr(decision, "model")
    assert hasattr(decision, "financial_score")
    assert hasattr(decision, "complexity_score")


def test_route_task_financial_routes_qwen():
    h = _harness()
    decision = h.route_task(_msg("process this payment transaction"))
    assert decision.model == MODEL_HIGH_RISK


def test_route_task_reasoning_routes_llama():
    h = _harness()
    decision = h.route_task(_msg("analyse and compare the two options"))
    assert decision.model == MODEL_MULTI_STEP


def test_route_task_simple_routes_granite():
    h = _harness()
    decision = h.route_task(_msg("what is 2 + 2?"))
    assert decision.model == MODEL_SIMPLE


def test_route_task_budget_exhausted_forces_granite():
    h = _harness(tokens_used=90_000, token_budget=100_000)
    decision = h.route_task(_msg("transfer $10000 payment transaction"))
    assert decision.model == MODEL_SIMPLE
    assert "budget_exhausted" in decision.reason


def test_route_task_passes_agent_and_session_ids():
    h = _harness(agent_id="my-agent", session_id="my-sess")
    decision = h.route_task(_msg("hello"))
    assert decision.agent_id == "my-agent"
    assert decision.session_id == "my-sess"


# ── execute_grammar_guided_action ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_returns_parsed_json():
    h = _harness()
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    payload_out = {"name": "Alice"}

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response(json.dumps(payload_out))

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        result = await h.execute_grammar_guided_action(
            "Extract name", schema=schema
        )

    assert result == payload_out


@pytest.mark.asyncio
async def test_execute_sends_guided_json_in_extra_body():
    h = _harness()
    schema = {"type": "object", "properties": {"amount": {"type": "number"}}}

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response('{"amount": 42}')

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        await h.execute_grammar_guided_action("Get amount", schema=schema)

    _, call_kwargs = mock_client.post.call_args
    sent_body = call_kwargs["json"]
    assert sent_body["extra_body"]["guided_json"] == schema


@pytest.mark.asyncio
async def test_execute_schema_as_string_is_decoded():
    h = _harness()
    schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
    schema_str = json.dumps(schema)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response('{"id": 7}')

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        result = await h.execute_grammar_guided_action(
            "Get id", schema=schema_str
        )

    assert result == {"id": 7}
    _, call_kwargs = mock_client.post.call_args
    sent_body = call_kwargs["json"]
    # Must be the decoded dict, not the raw string
    assert sent_body["extra_body"]["guided_json"] == schema


@pytest.mark.asyncio
async def test_execute_hc4_tenant_id_in_header():
    """HC-4: x-litellm-metadata must carry tenant_id on every call."""
    h = _harness(tenant_id="aaaa-bbbb-cccc-dddd")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response('{"ok": true}')

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        await h.execute_grammar_guided_action(
            "do something", schema={"type": "object"}
        )

    _, call_kwargs = mock_client.post.call_args
    metadata = json.loads(call_kwargs["headers"]["x-litellm-metadata"])
    assert metadata["tenant_id"] == "aaaa-bbbb-cccc-dddd"


@pytest.mark.asyncio
async def test_execute_no_messages_builds_single_turn():
    h = _harness()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response('{"x": 1}')

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        await h.execute_grammar_guided_action(
            "My prompt", schema={"type": "object"}, messages=None
        )

    _, call_kwargs = mock_client.post.call_args
    msgs = call_kwargs["json"]["messages"]
    assert msgs == [{"role": "user", "content": "My prompt"}]


@pytest.mark.asyncio
async def test_execute_with_messages_appends_prompt():
    h = _harness()
    history = [
        {"role": "user",      "content": "first turn"},
        {"role": "assistant", "content": "reply"},
    ]
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response('{"x": 2}')

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        await h.execute_grammar_guided_action(
            "second prompt", schema={"type": "object"}, messages=history
        )

    _, call_kwargs = mock_client.post.call_args
    msgs = call_kwargs["json"]["messages"]
    assert len(msgs) == 3
    assert msgs[-1] == {"role": "user", "content": "second prompt"}


@pytest.mark.asyncio
async def test_execute_updates_tokens_used():
    h = _harness()
    assert h.tokens_used == 0

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response(
        '{"result": "ok"}', prompt_tokens=30, completion_tokens=15
    )

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        await h.execute_grammar_guided_action(
            "compute", schema={"type": "object"}
        )

    assert h.tokens_used == 45


@pytest.mark.asyncio
async def test_execute_propagates_http_error():
    h = _harness()

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            await h.execute_grammar_guided_action(
                "do something", schema={"type": "object"}
            )


@pytest.mark.asyncio
async def test_execute_propagates_json_decode_error():
    h = _harness()

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _litellm_response("not-valid-json")

    with patch("model_harness.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        with pytest.raises(json.JSONDecodeError):
            await h.execute_grammar_guided_action(
                "do something", schema={"type": "object"}
            )
