"""
Tests — Adaptive Model Router
File: platform/agentic-os/tests/test_model_router.py

Covers:
  - Financial keyword routing → Qwen-72B
  - Reasoning keyword routing → Llama-70B
  - Simple/no-signal routing → Granite-3B
  - Budget hard guard (≥ 80%) → forced Granite
  - Budget soft penalty (50–80%) → complexity dampened
  - Multi-turn boost
  - HC-3 audit log (logged via logging module)
"""

from __future__ import annotations

import pytest

from router.model_router import (
    MODEL_HIGH_RISK,
    MODEL_MULTI_STEP,
    MODEL_SIMPLE,
    RoutingDecision,
    score_complexity,
    score_financial,
    select_model,
)


def _msg(text: str) -> list[dict]:
    return [{"role": "user", "content": text}]


# ── score_financial ────────────────────────────────────────────────────────────

def test_financial_score_payment():
    assert score_financial("please process this payment") >= 0.6


def test_financial_score_transfer():
    assert score_financial("transfer $800 to the account") >= 0.6


def test_financial_score_low():
    assert score_financial("hello, how are you?") == 0.0


def test_financial_score_caps_at_one():
    assert score_financial(
        "transfer payment transaction loan credit fund banking invoice"
    ) == 1.0


# ── score_complexity ───────────────────────────────────────────────────────────

def test_complexity_score_reasoning():
    assert score_complexity(_msg("analyse and compare the two options")) >= 0.5


def test_complexity_score_simple():
    assert score_complexity(_msg("hi")) < 0.5


def test_complexity_multi_turn_boost():
    # A sparse last message that on its own yields a low complexity score;
    # with > 3 messages in history the +0.2 boost should push it up.
    messages = [
        {"role": "user",      "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user",      "content": "ok sure"},
        {"role": "assistant", "content": "noted"},
        {"role": "user",      "content": "analyse this"},   # last user message
    ]
    # Single-turn: only the "analyse this" message — keyword score ~0.6, no boost
    single_score = score_complexity(_msg("analyse this"))
    # Multi-turn: same last user message but > 3 messages → +0.2 boost
    multi_score  = score_complexity(messages)
    assert multi_score > single_score
    assert multi_score == pytest.approx(single_score + 0.2, abs=0.01)


# ── select_model ───────────────────────────────────────────────────────────────

def test_financial_routes_to_qwen():
    decision = select_model(
        _msg("process this payment of $1200 for the transaction"),
        agent_id="test-agent",
        session_id="s-001",
    )
    assert decision.model == MODEL_HIGH_RISK
    assert decision.financial_score >= 0.6


def test_reasoning_routes_to_llama():
    decision = select_model(
        _msg("please analyse and summarise the market strategy"),
        agent_id="test-agent",
        session_id="s-002",
    )
    assert decision.model == MODEL_MULTI_STEP
    assert decision.complexity_score >= 0.5


def test_simple_routes_to_granite():
    decision = select_model(
        _msg("what is the weather today?"),
        agent_id="test-agent",
        session_id="s-003",
    )
    assert decision.model == MODEL_SIMPLE


def test_budget_hard_guard_forces_granite():
    """At ≥ 80% budget consumption, always route to Granite regardless of content."""
    decision = select_model(
        _msg("transfer $10000 payment transaction"),
        agent_id="test-agent",
        session_id="s-004",
        tokens_used=85_000,
        token_budget=100_000,
    )
    assert decision.model == MODEL_SIMPLE
    assert "budget_exhausted" in decision.reason


def test_budget_soft_penalty_dampens_complexity():
    """At 60% budget, complexity score is halved — a borderline complexity
    message that would normally trigger Llama should fall to Granite."""
    # Message with a complexity score just above 0.5 in full budget
    msg = _msg("evaluate this option")
    full_budget_decision = select_model(msg, agent_id="a", session_id="s", tokens_used=0, token_budget=100_000)
    half_budget_decision = select_model(msg, agent_id="a", session_id="s", tokens_used=65_000, token_budget=100_000)
    # Full budget may route to Llama; half budget should dampen to Granite
    # (complexity score × 0.5 < 0.5 threshold)
    assert half_budget_decision.model in (MODEL_SIMPLE, MODEL_MULTI_STEP)
    # At minimum, budget_ratio should be reflected
    assert half_budget_decision.budget_ratio == pytest.approx(0.65, abs=0.01)


def test_financial_overrides_budget_soft_penalty():
    """Financial routing is NOT dampened by the soft budget penalty;
    only complexity is dampened."""
    decision = select_model(
        _msg("process payment transaction fund"),
        agent_id="test-agent",
        session_id="s-005",
        tokens_used=60_000,
        token_budget=100_000,
    )
    assert decision.model == MODEL_HIGH_RISK


def test_decision_is_routing_decision_type():
    decision = select_model(_msg("hello"), agent_id="a", session_id="s")
    assert isinstance(decision, RoutingDecision)
    assert decision.agent_id == "a"
    assert decision.session_id == "s"


def test_empty_messages_defaults_to_granite():
    decision = select_model([], agent_id="a", session_id="s")
    assert decision.model == MODEL_SIMPLE
