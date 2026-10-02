"""
i3 Agentic AI OS — Adaptive Model Router
File: platform/agentic-os/router/model_router.py

Adaptive routing matrix: selects the LLM backend based on a scored
combination of task complexity, financial risk, and token budget.

Decision table (from agentic-os-supervisor.yaml model_routing):
  ┌─────────────────────────────┬──────────────────────────┬────────────────────────┐
  │ Condition                   │ Model                    │ Backend                │
  ├─────────────────────────────┼──────────────────────────┼────────────────────────┤
  │ financial risk score ≥ 0.6  │ qwen-2.5-72b-instruct   │ vLLM GPU (Qwen pod)   │
  │ complexity score ≥ 0.5      │ llama-3.3-70b-instruct  │ vLLM GPU (Llama pod)  │
  │ all others (fast / simple)  │ ibm-granite-3b-instruct  │ Ollama CPU             │
  └─────────────────────────────┴──────────────────────────┴────────────────────────┘

Scoring algorithm:
  financial_score = weighted keyword hit rate across {financial_signals}
  complexity_score = weighted keyword hit rate across {reasoning_signals}
                     + penalty-free boost for message count > 3 (multi-turn)
  budget_factor   = 1.0 if tokens_used < 0.5 × budget
                    0.5 if tokens_used ∈ [0.5, 0.8) × budget   (throttle down)
                    0.0 if tokens_used ≥ 0.8 × budget           (force Granite)

HC-3: every routing decision is logged with agent_id, session_id, and
      selected_model for audit trail in Agent Registry decision log.
HC-4: tenant_id is passed through but does not influence model selection
      (model routing is tenant-agnostic; cost policy is per-tenant).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("agentic-os.router")

# ── Model identifiers ─────────────────────────────────────────────────────────
MODEL_HIGH_RISK   = "qwen-2.5-72b-instruct"    # GPU — Qwen pod (financial decisions)
MODEL_MULTI_STEP  = "llama-3.3-70b-instruct"   # GPU — Llama pod (complex reasoning)
MODEL_SIMPLE      = "ibm-granite-3b-instruct"  # CPU — Ollama (fast, cheap)

# ── Scoring vocabulary ────────────────────────────────────────────────────────
# Weighted financial signal map: keyword → score increment (0.0–1.0)
_FINANCIAL_SIGNALS: dict[str, float] = {
    "transfer":      0.8,
    "payment":       0.8,
    "transaction":   0.8,
    "approval":      0.5,
    "financial":     0.7,
    "banking":       0.8,
    "loan":          0.8,
    "credit":        0.7,
    "debit":         0.7,
    "fund":          0.6,
    "invoice":       0.6,
    "budget":        0.5,
    "revenue":       0.5,
    "arr":           0.5,    # annual recurring revenue
    "sync":          0.3,    # ibm_sales_cloud.sync context
    "ibm sales":     0.6,
}

# Weighted complexity signal map: keyword → score increment
_REASONING_SIGNALS: dict[str, float] = {
    "analyse":       0.6,
    "analyze":       0.6,
    "compare":       0.5,
    "plan":          0.5,
    "strategy":      0.6,
    "evaluate":      0.6,
    "research":      0.5,
    "summarise":     0.5,
    "summarize":     0.5,
    "explain":       0.4,
    "recommend":     0.5,
    "diagnose":      0.6,
    "optimise":      0.5,
    "optimize":      0.5,
    "multi-step":    0.7,
    "step by step":  0.7,
}

# Score thresholds
_FINANCIAL_THRESHOLD  = 0.6
_COMPLEXITY_THRESHOLD = 0.5
_BUDGET_THROTTLE_SOFT = 0.50   # above this: downgrade complexity signals only
_BUDGET_THROTTLE_HARD = 0.80   # above this: force Granite regardless


@dataclass
class RoutingDecision:
    """Immutable result of a model routing evaluation."""
    model:            str
    financial_score:  float
    complexity_score: float
    budget_ratio:     float
    reason:           str
    agent_id:         str
    session_id:       str


def score_financial(text: str) -> float:
    """
    Return a financial risk score in [0.0, 1.0] based on keyword presence.
    Caps at 1.0 — individual signals are additive but bounded.
    """
    text_lower = text.lower()
    total = sum(
        weight for kw, weight in _FINANCIAL_SIGNALS.items()
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)
    )
    return min(total, 1.0)


def score_complexity(messages: list[dict[str, Any]]) -> float:
    """
    Return a reasoning complexity score in [0.0, 1.0].
    Combines:
      - keyword hit score on the last user message
      - multi-turn boost (+0.2) when conversation history has > 3 messages
    """
    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    ).lower()

    keyword_score = sum(
        weight for kw, weight in _REASONING_SIGNALS.items()
        if re.search(r"\b" + re.escape(kw) + r"\b", last_user)
    )

    # Multi-turn boost: longer conversations warrant heavier model
    multi_turn_boost = 0.2 if len(messages) > 3 else 0.0

    return min(keyword_score + multi_turn_boost, 1.0)


def select_model(
    messages:       list[dict[str, Any]],
    *,
    agent_id:       str,
    session_id:     str,
    tokens_used:    int = 0,
    token_budget:   int = 100_000,
) -> RoutingDecision:
    """
    Adaptive model routing entry point.

    Algorithm:
      1. Compute budget_ratio = tokens_used / token_budget
      2. Hard budget guard: if budget_ratio ≥ 0.80 → force Granite (cheapest)
      3. Score last user message for financial risk and reasoning complexity
      4. Apply soft budget penalty: if budget_ratio ∈ [0.50, 0.80) halve complexity score
      5. Route:
           financial_score ≥ 0.6              → Qwen-72B  (high-risk model)
           complexity_score ≥ 0.5             → Llama-70B (reasoning model)
           otherwise                          → Granite-3B (fast/cheap)

    HC-3: result is logged with agent_id + session_id for audit trace.

    Returns:
        RoutingDecision with selected model and diagnostic scores.
    """
    budget_ratio = tokens_used / max(token_budget, 1)

    # Hard budget guard
    if budget_ratio >= _BUDGET_THROTTLE_HARD:
        decision = RoutingDecision(
            model=MODEL_SIMPLE,
            financial_score=0.0,
            complexity_score=0.0,
            budget_ratio=budget_ratio,
            reason="budget_exhausted (≥80% consumed) — forced Granite",
            agent_id=agent_id,
            session_id=session_id,
        )
        _log_decision(decision)
        return decision

    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    )

    fin_score  = score_financial(last_user)
    comp_score = score_complexity(messages)

    # Soft budget penalty: dampen complexity routing when >50% budget consumed
    if budget_ratio >= _BUDGET_THROTTLE_SOFT:
        comp_score *= 0.5

    # Route selection
    if fin_score >= _FINANCIAL_THRESHOLD:
        model  = MODEL_HIGH_RISK
        reason = f"financial_score={fin_score:.2f} ≥ {_FINANCIAL_THRESHOLD}"
    elif comp_score >= _COMPLEXITY_THRESHOLD:
        model  = MODEL_MULTI_STEP
        reason = f"complexity_score={comp_score:.2f} ≥ {_COMPLEXITY_THRESHOLD}"
    else:
        model  = MODEL_SIMPLE
        reason = f"fin={fin_score:.2f} comp={comp_score:.2f} — below thresholds"

    decision = RoutingDecision(
        model=model,
        financial_score=fin_score,
        complexity_score=comp_score,
        budget_ratio=budget_ratio,
        reason=reason,
        agent_id=agent_id,
        session_id=session_id,
    )
    _log_decision(decision)
    return decision


def _log_decision(d: RoutingDecision) -> None:
    """HC-3: Log every routing decision for audit trail."""
    log.info(
        "model_routing agent=%s session=%s model=%s reason=%r "
        "fin=%.2f comp=%.2f budget_pct=%.0f%%",
        d.agent_id, d.session_id, d.model, d.reason,
        d.financial_score, d.complexity_score, d.budget_ratio * 100,
    )
