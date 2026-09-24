"""
platform/agentops/tests/test_agentops.py

Unit tests for the AgentOps weekly review pack generator.
All tests are offline (no DB, no S3, no network).

Run: pytest platform/agentops/tests/ -v
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import via the _i3_agentops_ alias registered by conftest.py
# (avoids shadowing the stdlib `platform` module)
# ---------------------------------------------------------------------------

_risk   = importlib.import_module("_i3_agentops_.risk_register")
_report = importlib.import_module("_i3_agentops_.report")
_pack   = importlib.import_module("_i3_agentops_.review_pack")
_cli    = importlib.import_module("_i3_agentops_.cli")

RISK_BASELINE  = _risk.RISK_BASELINE
_detect_drift  = _risk._detect_drift
build_risk_register = _risk.build_risk_register
render_html    = _report.render_html
fetch_eval_trend = _pack.fetch_eval_trend
_parse_args    = _cli._parse_args


# ---------------------------------------------------------------------------
# risk_register tests
# ---------------------------------------------------------------------------

def test_risk_register_has_five_items():
    items = build_risk_register(sensors={})
    assert len(items) == 5


def test_risk_register_no_duplicate_ids():
    items = build_risk_register(sensors={})
    ids = [r["id"] for r in items]
    assert len(ids) == len(set(ids))


def test_risk_register_sorted_by_score():
    items = build_risk_register(sensors={})
    scores = [r["score"] for r in items]
    assert scores == sorted(scores, reverse=True)


def test_risk_register_all_required_fields():
    required = {
        "id", "title", "category", "likelihood", "impact",
        "score", "owner", "controls", "status", "last_reviewed",
        "drift", "drift_note",
    }
    for item in build_risk_register(sensors={}):
        assert required <= set(item.keys()), f"{item['id']} missing fields"


def test_drift_degrading_numeric():
    defn = RISK_BASELINE["R-004"]  # tenants_over_80pct_budget, warn=2
    drift, note = _detect_drift("R-004", defn, {"tenants_over_80pct_budget": 3})
    assert drift == "DEGRADING"
    assert "3" in note


def test_drift_improving_numeric():
    defn = RISK_BASELINE["R-004"]
    drift, note = _detect_drift("R-004", defn, {"tenants_over_80pct_budget": 0})
    assert drift == "IMPROVING"


def test_drift_stable_no_sensor():
    defn = RISK_BASELINE["R-001"]
    drift, note = _detect_drift("R-001", defn, {})
    assert drift == "STABLE"
    assert "not available" in note.lower()


def test_drift_boolean_degrading():
    defn = RISK_BASELINE["R-005"]  # ragas_passing, warn=False
    drift, note = _detect_drift("R-005", defn, {"ragas_passing": False})
    assert drift == "DEGRADING"


def test_drift_boolean_improving():
    defn = RISK_BASELINE["R-005"]
    drift, note = _detect_drift("R-005", defn, {"ragas_passing": True})
    assert drift == "IMPROVING"


def test_build_risk_register_with_live_sensors(monkeypatch):
    monkeypatch.setenv("SENSOR_LOBSTER_DENY_RATE_PCT", "7.5")   # > warn(5.0) → DEGRADING
    monkeypatch.setenv("SENSOR_RLS_VIOLATION_COUNT", "0")
    monkeypatch.setenv("SENSOR_L2_L3_MANIFEST_COUNT", "0")
    monkeypatch.setenv("SENSOR_TENANTS_OVER_80PCT_BUDGET", "0")
    monkeypatch.setenv("SENSOR_RAGAS_PASSING", "true")
    items = build_risk_register()
    r001 = next(i for i in items if i["id"] == "R-001")
    assert r001["drift"] == "DEGRADING"


# ---------------------------------------------------------------------------
# report.py tests
# ---------------------------------------------------------------------------

def _sample_pack() -> dict:
    return {
        "generated_at": "2026-10-05T04:00:00+00:00",
        "week": "W41-2026",
        "tenant_scope": "all",
        "autonomy_rates": [
            {
                "agent_id": "admissions-agent",
                "tenant_id": "aaaa0000-0000-0000-0000-000000000001",
                "total_decisions": 200,
                "autonomous_successes": 185,
                "human_overrides": 15,
                "autonomy_rate_pct": 92.5,
            }
        ],
        "gate_latency": [
            {
                "agent_id": "admissions-agent",
                "tenant_id": "aaaa0000-0000-0000-0000-000000000001",
                "approval_count": 15,
                "avg_latency_sec": 42.3,
                "p95_latency_sec": 90.1,
            }
        ],
        "spend_vs_budget": [
            {
                "tenant_name": "TestU",
                "year_month": "2026-10",
                "tokens_used": 80000,
                "token_budget": 100000,
                "budget_utilisation_pct": 80.0,
                "over_quota_hits": 0,
                "request_count": 150,
            }
        ],
        "eval_trend": {
            "status": "PASS",
            "gate": "P1-GATE-10",
            "model": "granite-nano",
            "n_queries": 10,
            "metrics": {
                "faithfulness": 0.87,
                "answer_relevancy": 0.81,
                "context_precision": 0.79,
            },
            "passing": True,
        },
        "audit_anomalies": [],
        "risk_register": build_risk_register(sensors={
            "lobster_trap_deny_rate_pct": 0.3,
            "rls_violation_count": 0,
            "l2_l3_manifest_count": 0,
            "tenants_over_80pct_budget": 1,
            "ragas_passing": True,
        }),
    }


def test_render_html_returns_string():
    doc = render_html(_sample_pack())
    assert isinstance(doc, str)
    assert len(doc) > 1000


def test_render_html_contains_week():
    doc = render_html(_sample_pack())
    assert "W41-2026" in doc


def test_render_html_contains_agent():
    doc = render_html(_sample_pack())
    assert "admissions-agent" in doc


def test_render_html_no_script_tags():
    doc = render_html(_sample_pack())
    assert "<script" not in doc.lower()


def test_render_html_pass_badge():
    doc = render_html(_sample_pack())
    assert "PASS" in doc


def test_render_html_empty_anomalies_shows_check():
    doc = render_html(_sample_pack())
    assert "No FAILURE" in doc or "FAILURE" not in doc


def test_render_html_six_sections():
    doc = render_html(_sample_pack())
    for i in range(1, 7):
        assert f'id="s{i}"' in doc


# ---------------------------------------------------------------------------
# CLI argument parsing tests (offline)
# ---------------------------------------------------------------------------

def test_cli_defaults():
    args = _parse_args([])
    assert args.upload is False
    assert args.json_only is False
    assert args.html_only is False


def test_cli_flags():
    args = _parse_args(["--json-only", "--upload", "--week", "W99-2099"])
    assert args.json_only is True
    assert args.upload is True
    assert args.week == "W99-2099"


def test_cli_tenants_parsed():
    args = _parse_args(["--tenants", "aaaa-1111,bbbb-2222"])
    assert args.tenants == "aaaa-1111,bbbb-2222"


# ---------------------------------------------------------------------------
# review_pack — fetch_eval_trend (file-based, no DB/S3)
# ---------------------------------------------------------------------------

def test_fetch_eval_trend_from_file(tmp_path):
    evidence = {
        "gate": "P1-GATE-10",
        "status": "PASS",
        "model": "granite-nano",
        "faithfulness": 0.85,
        "answer_relevancy": 0.78,
        "context_precision": 0.80,
        "n_queries": 10,
    }
    p = tmp_path / "ragas.json"
    p.write_text(json.dumps(evidence), encoding="utf-8")
    result = fetch_eval_trend(str(p))
    assert result["passing"] is True
    assert result["metrics"]["faithfulness"] == 0.85


def test_fetch_eval_trend_missing_file():
    result = fetch_eval_trend("/nonexistent/path.json")
    assert result["status"] == "NO_EVIDENCE"


def test_fetch_eval_trend_failing_scores(tmp_path):
    evidence = {
        "gate": "P1-GATE-10",
        "status": "FAIL",
        "model": "granite-nano",
        "faithfulness": 0.60,     # below 0.80
        "answer_relevancy": 0.70,  # below 0.75
        "context_precision": 0.65,
        "n_queries": 10,
    }
    p = tmp_path / "ragas_fail.json"
    p.write_text(json.dumps(evidence), encoding="utf-8")
    result = fetch_eval_trend(str(p))
    assert result["passing"] is False
