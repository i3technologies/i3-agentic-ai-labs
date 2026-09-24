"""
platform/agentops/risk_register.py — AgentOps risk register with drift detection

Maintains the top-5 standing risks for the i3 AI Platform post-launch.
Each risk entry carries:
  - id          short stable identifier
  - title       one-line human label
  - category    SECURITY | COMPLIANCE | OPERATIONAL | FINANCIAL | STRATEGIC
  - likelihood  1–5 (increasing probability)
  - impact      1–5 (increasing severity)
  - score       likelihood * impact
  - owner       owning role
  - controls    list of active mitigating controls
  - status      OPEN | MITIGATED | ACCEPTED | CLOSED
  - last_reviewed ISO-8601 date (updated each time the pack runs)
  - drift       STABLE | IMPROVING | DEGRADING | NEW
  - drift_note  one-line explanation of drift direction

Drift detection compares the current run's programmatic sensor readings
(queried inline from the metrics/DB) against the expected thresholds
stored in RISK_BASELINE below.  Where live data is unavailable, drift
defaults to STABLE and a note is appended.

HC-3 enforcement: no risk item may approve an autonomy tier upgrade without
  verified evaluation evidence — this register carries R-003 to enforce it.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Baseline thresholds (what "normal" looks like after a stable launch week)
# ---------------------------------------------------------------------------

RISK_BASELINE: dict[str, dict[str, Any]] = {
    "R-001": {
        "title":      "Prompt-injection bypass via crafted user input",
        "category":   "SECURITY",
        "likelihood": 3,
        "impact":     5,
        "owner":      "Security Engineer",
        "controls": [
            "12-pattern Lobster Trap firewall on all user inputs (TS + Python)",
            "Langfuse trace review for anomalous completions",
            "WORM audit trail for all DENIED outcomes",
        ],
        "status":     "OPEN",
        "threshold_key":   "lobster_trap_deny_rate_pct",
        "threshold_warn":  5.0,   # >5 % denials in a week → DEGRADING
        "threshold_ok":    1.0,   # <1 % → IMPROVING
    },
    "R-002": {
        "title":      "Tenant data leakage across RLS boundary",
        "category":   "COMPLIANCE",
        "likelihood": 2,
        "impact":     5,
        "owner":      "Platform Architect",
        "controls": [
            "PostgreSQL RLS on all billing.* and agent_registry.* tables (HC-4)",
            "app.tenant_id SET on every DB connection",
            "CI RLS smoke test in test_metering_spine.py",
        ],
        "status":     "OPEN",
        "threshold_key":   "rls_violation_count",
        "threshold_warn":  1,     # any violation → DEGRADING (fail-critical)
        "threshold_ok":    0,
    },
    "R-003": {
        "title":      "Unauthorised autonomy tier promotion (HC-3)",
        "category":   "COMPLIANCE",
        "likelihood": 2,
        "impact":     4,
        "owner":      "CTO / Philip Mukiti",
        "controls": [
            "AgentManifest.autonomy_tier regex enforced to ^(L0|L1)$ by Agent Registry",
            "No L2/L3 tier accepted in DB schema without gate-check evidence",
            "Weekly review pack flags any manifest with tier outside L0/L1",
        ],
        "status":     "OPEN",
        "threshold_key":   "l2_l3_manifest_count",
        "threshold_warn":  1,     # any L2/L3 manifest → DEGRADING
        "threshold_ok":    0,
    },
    "R-004": {
        "title":      "Token-budget exhaustion degrading service SLA",
        "category":   "FINANCIAL",
        "likelihood": 3,
        "impact":     3,
        "owner":      "Platform Ops",
        "controls": [
            "LiteLLM per-tenant max_budget with HTTP 429 hard stop",
            "Prometheus TenantTokenBudgetHigh / Exhausted alerts at 80 % / 100 %",
            "Weekly spend-vs-budget section in this review pack",
        ],
        "status":     "OPEN",
        "threshold_key":   "tenants_over_80pct_budget",
        "threshold_warn":  2,     # ≥2 tenants above 80 % → DEGRADING
        "threshold_ok":    0,
    },
    "R-005": {
        "title":      "RAGAS eval-suite regression below production thresholds",
        "category":   "OPERATIONAL",
        "likelihood": 2,
        "impact":     3,
        "owner":      "ML Engineer",
        "controls": [
            "RAGAS gate-evidence JSON checked every deploy (faithfulness ≥0.80, relevancy ≥0.75)",
            "Eval trend section in this review pack",
            "Promptfoo regression suite in CI (platform/testing/promptfoo-config.yaml)",
        ],
        "status":     "OPEN",
        "threshold_key":   "ragas_passing",
        "threshold_warn":  False,  # not passing → DEGRADING
        "threshold_ok":    True,
    },
}


# ---------------------------------------------------------------------------
# Live sensor readings (best-effort; fall back to None gracefully)
# ---------------------------------------------------------------------------

def _read_sensors() -> dict[str, Any]:
    """
    Attempt to read live sensor values from the environment / metrics.

    Returns a dict keyed by threshold_key.  Missing values are None,
    which causes drift to fall back to STABLE.

    In production these values are injected by the CronJob as env vars
    populated by a pre-step Prometheus query (see cronjob-weekly-pack.yaml).
    """
    def _env_float(key: str) -> float | None:
        v = os.environ.get(key)
        return float(v) if v is not None else None

    def _env_int(key: str) -> int | None:
        v = os.environ.get(key)
        return int(v) if v is not None else None

    def _env_bool(key: str) -> bool | None:
        v = os.environ.get(key)
        if v is None:
            return None
        return v.lower() in ("1", "true", "yes", "pass")

    return {
        "lobster_trap_deny_rate_pct": _env_float("SENSOR_LOBSTER_DENY_RATE_PCT"),
        "rls_violation_count":        _env_int("SENSOR_RLS_VIOLATION_COUNT"),
        "l2_l3_manifest_count":       _env_int("SENSOR_L2_L3_MANIFEST_COUNT"),
        "tenants_over_80pct_budget":  _env_int("SENSOR_TENANTS_OVER_80PCT_BUDGET"),
        "ragas_passing":              _env_bool("SENSOR_RAGAS_PASSING"),
    }


# ---------------------------------------------------------------------------
# Drift logic
# ---------------------------------------------------------------------------

def _detect_drift(
    risk_id: str,
    risk_def: dict[str, Any],
    sensors: dict[str, Any],
) -> tuple[str, str]:
    """
    Return (drift_label, drift_note) for a single risk item.

    Drift is:
      DEGRADING  — sensor exceeds warn threshold
      IMPROVING  — sensor at or below ok threshold
      STABLE     — in between, or sensor unavailable
    """
    key = risk_def.get("threshold_key")
    if key is None:
        return "STABLE", "No sensor configured."

    value = sensors.get(key)
    if value is None:
        return "STABLE", f"Sensor '{key}' not available this cycle."

    warn = risk_def["threshold_warn"]
    ok   = risk_def["threshold_ok"]

    # Boolean sensor (e.g. ragas_passing)
    if isinstance(warn, bool):
        if value == warn:   # warn is False → degrading when value is False
            return (
                "DEGRADING",
                f"RAGAS eval suite is not passing thresholds (sensor={value}).",
            )
        return "IMPROVING", f"RAGAS eval suite is passing (sensor={value})."

    # Numeric sensor
    if value >= warn:
        return (
            "DEGRADING",
            f"Sensor '{key}' = {value} ≥ warn threshold {warn}.",
        )
    if value <= ok:
        return (
            "IMPROVING",
            f"Sensor '{key}' = {value} ≤ ok threshold {ok}.",
        )
    return "STABLE", f"Sensor '{key}' = {value} within normal range."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_risk_register(sensors: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """
    Build the top-5 risk register with current drift status.

    sensors: optional pre-loaded sensor dict (for testing).
             If None, sensors are read from environment variables.

    Returns a list of risk dicts sorted by score DESC, length ≤ 5.
    """
    if sensors is None:
        sensors = _read_sensors()

    now_iso = datetime.now(tz=timezone.utc).date().isoformat()
    items: list[dict[str, Any]] = []

    for risk_id, defn in RISK_BASELINE.items():
        drift, drift_note = _detect_drift(risk_id, defn, sensors)
        score = defn["likelihood"] * defn["impact"]
        items.append({
            "id":            risk_id,
            "title":         defn["title"],
            "category":      defn["category"],
            "likelihood":    defn["likelihood"],
            "impact":        defn["impact"],
            "score":         score,
            "owner":         defn["owner"],
            "controls":      defn["controls"],
            "status":        defn["status"],
            "last_reviewed": now_iso,
            "drift":         drift,
            "drift_note":    drift_note,
        })

    # Sort by score descending; ties broken by id for determinism
    items.sort(key=lambda r: (-r["score"], r["id"]))
    return items[:5]
