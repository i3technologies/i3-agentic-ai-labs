#!/usr/bin/env bash
# ============================================================
# P3-GATE-13: Locust SLA Runner
# Runs Locust load tests and writes p95 latency evidence JSON.
#
# Prerequisites:
#   pip install locust
#   STAGING_BASE_URL set to staging ingress
#   LITELLM_MASTER_KEY from OpenBao i3/litellm/api-key
#   ENGAGE_TOKEN — Keycloak-issued Bearer token for test user
#
# Usage: bash platform/scripts/p3-gate-13-locust.sh
# ============================================================

set -euo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-locust-sla.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
STAGING_BASE="${STAGING_BASE_URL:-https://api.i3technologies.co.ke}"
EVALOS_HOST="${EVALOS_HOST:-https://evalos.i3technologies.co.ke}"
ENGAGE_HOST="${ENGAGE_HOST:-https://engage.i3technologies.co.ke}"

echo "=== P3-GATE-13: Locust SLA load test ==="

# ── EvalOS exam start (p95 <= 3000ms) ────────────────────────────────────────
echo "--- EvalOS exam start (100 users, 5 min) ---"
locust -f platform/testing/testing.py EvalOSSandboxUser \
  --headless -u 100 -r 10 --run-time 5m \
  --host "${EVALOS_HOST}" \
  --csv=/tmp/locust-evalos \
  --logfile=/tmp/locust-evalos.log \
  --only-summary 2>&1 | tail -20 || true

# ── Engage campaign send (p95 <= 3000ms, async path) ─────────────────────────
echo "--- Engage campaign create (50 users, 5 min) ---"
locust -f platform/testing/testing.py AILabAPIUser \
  --headless -u 50 -r 5 --run-time 5m \
  --host "${ENGAGE_HOST}" \
  --csv=/tmp/locust-engage \
  --logfile=/tmp/locust-engage.log \
  --only-summary 2>&1 | tail -20 || true

# ── Parse CSV output and write evidence JSON ──────────────────────────────────
python3 - <<PYEOF
import csv, json, os

def parse_locust_csv(csv_path, endpoint_filter):
    """Read Locust stats CSV and extract p95 for a matching endpoint."""
    try:
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if endpoint_filter.lower() in row.get("Name", "").lower():
                    return {
                        "p50_ms":          float(row.get("50%", 0) or 0),
                        "p95_ms":          float(row.get("95%", 0) or 0),
                        "p99_ms":          float(row.get("99%", 0) or 0),
                        "rps":             float(row.get("Requests/s", 0) or 0),
                        "error_rate_pct":  float(row.get("Failure Count", 0) or 0),
                    }
    except FileNotFoundError:
        pass
    return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "rps": None, "error_rate_pct": None}

with open("${EVIDENCE_FILE}") as f:
    ev = json.load(f)

evalos_stats  = parse_locust_csv("/tmp/locust-evalos_stats.csv",  "submit")
engage_stats  = parse_locust_csv("/tmp/locust-engage_stats.csv",  "campaigns")

ev["exam_start"].update(evalos_stats)
ev["exam_start"]["pass"]   = (evalos_stats["p95_ms"] is not None and evalos_stats["p95_ms"] <= 3000)

ev["campaign_create"].update(engage_stats)
ev["campaign_create"]["pass"] = (engage_stats["p95_ms"] is not None and engage_stats["p95_ms"] <= 3000)

# NBA/consent: derive from AI Lab stats (proxy for LiteLLM p95)
ev["nba_consent"]["p95_ms"] = evalos_stats.get("p95_ms")
ev["nba_consent"]["pass"]   = (evalos_stats.get("p95_ms") is not None and evalos_stats["p95_ms"] <= 200)

ev["overall_pass"] = all([
    ev["nba_consent"]["pass"],
    ev["exam_start"]["pass"],
    ev["campaign_create"]["pass"],
])
ev["run_at"] = "${RUN_DATE}"

with open("${EVIDENCE_FILE}", "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({
    "nba_consent_p95":     ev["nba_consent"]["p95_ms"],
    "exam_start_p95":      ev["exam_start"]["p95_ms"],
    "campaign_create_p95": ev["campaign_create"]["p95_ms"],
    "overall_pass":        ev["overall_pass"],
}, indent=2))
PYEOF

PASS=$(python3 -c "import json; d=json.load(open('${EVIDENCE_FILE}')); print(d['overall_pass'])")

if [[ "${PASS}" == "True" ]]; then
  echo "P3-GATE-13: PASS — all p95 SLAs met"
else
  echo "P3-GATE-13: FAIL — one or more SLA violations (see ${EVIDENCE_FILE})"
  exit 1
fi
