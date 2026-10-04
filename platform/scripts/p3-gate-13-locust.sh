#!/usr/bin/env bash
# ============================================================
# P3-GATE-13: Locust SLA Runner
# Installs locust if needed, runs load tests against staging,
# writes p95 latency evidence to platform/docs/verification/p3-locust-sla.json
#
# Usage (from repo root):
#   bash platform/scripts/p3-gate-13-locust.sh
#
# Env vars:
#   EVALOS_HOST    — default: https://evalos.i3technologies.co.ke
#   ENGAGE_HOST    — default: https://engage.i3technologies.co.ke
#   LITELLM_MASTER_KEY — LiteLLM key for AI Lab user
# ============================================================

set -euo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-locust-sla.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# ── Install locust if not present ─────────────────────────────────────────────
if ! command -v locust &>/dev/null && ! python3 -m locust --version &>/dev/null 2>&1; then
  echo "--- Installing locust ---"
  pip3 install locust --quiet
fi

# Ensure locust is on PATH (pip user installs go to ~/.local/bin)
export PATH="${HOME}/.local/bin:${PATH}"

EVALOS_HOST="${EVALOS_HOST:-https://evalos.i3technologies.co.ke}"
ENGAGE_HOST="${ENGAGE_HOST:-https://engage.i3technologies.co.ke}"

echo "=== P3-GATE-13: Locust SLA load test ==="
echo "    EvalOS: ${EVALOS_HOST}"
echo "    Engage: ${ENGAGE_HOST}"

# ── EvalOS exam start (p95 ≤ 3000ms) ─────────────────────────────────────────
echo "--- EvalOS exam start (100 users, 2 min) ---"
python3 -m locust -f platform/testing/testing.py EvalOSSandboxUser \
  --headless -u 100 -r 10 --run-time 2m \
  --host "${EVALOS_HOST}" \
  --csv=/tmp/locust-evalos \
  --only-summary 2>&1 | tail -20 || true

# ── Engage campaign (p95 ≤ 3000ms) ───────────────────────────────────────────
echo "--- Engage campaign (50 users, 2 min) ---"
python3 -m locust -f platform/testing/testing.py AILabAPIUser \
  --headless -u 50 -r 5 --run-time 2m \
  --host "${ENGAGE_HOST}" \
  --csv=/tmp/locust-engage \
  --only-summary 2>&1 | tail -20 || true

# ── Parse results and write evidence JSON ────────────────────────────────────
python3 - <<PYEOF
import csv, json, os

def parse_csv(path, name_filter):
    try:
        with open(path) as f:
            for row in csv.DictReader(f):
                if name_filter.lower() in row.get("Name", "").lower():
                    return {
                        "p50_ms":         _f(row.get("50%")),
                        "p95_ms":         _f(row.get("95%")),
                        "p99_ms":         _f(row.get("99%")),
                        "rps":            _f(row.get("Requests/s")),
                        "error_rate_pct": _f(row.get("Failure Count")),
                    }
    except FileNotFoundError:
        pass
    return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "rps": None, "error_rate_pct": None}

def _f(v):
    try: return float(v or 0)
    except: return None

evalos = parse_csv("/tmp/locust-evalos_stats.csv",  "submit")
engage = parse_csv("/tmp/locust-engage_stats.csv",  "campaign")

try:
    with open("${EVIDENCE_FILE}") as f:
        ev = json.load(f)
except Exception:
    ev = {"nba_consent": {}, "exam_start": {}, "campaign_create": {}}

ev["exam_start"].update(evalos)
ev["exam_start"]["pass"] = evalos["p95_ms"] is not None and evalos["p95_ms"] <= 3000

ev["campaign_create"].update(engage)
ev["campaign_create"]["pass"] = engage["p95_ms"] is not None and engage["p95_ms"] <= 3000

# NBA/consent uses EvalOS p95 as proxy (LiteLLM fast path)
ev["nba_consent"]["p95_ms"] = evalos.get("p95_ms")
ev["nba_consent"]["pass"]   = evalos.get("p95_ms") is not None and evalos["p95_ms"] <= 200

ev["overall_pass"] = all([
    ev["nba_consent"].get("pass", False),
    ev["exam_start"].get("pass", False),
    ev["campaign_create"].get("pass", False),
])
ev["run_at"] = "${RUN_DATE}"

with open("${EVIDENCE_FILE}", "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({
    "exam_start_p95":      ev["exam_start"].get("p95_ms"),
    "campaign_create_p95": ev["campaign_create"].get("p95_ms"),
    "overall_pass":        ev["overall_pass"],
}, indent=2))
PYEOF

PASS=$(python3 -c "import json; d=json.load(open('${EVIDENCE_FILE}')); print(d.get('overall_pass', False))")

if [[ "${PASS}" == "True" ]]; then
  echo "P3-GATE-13: PASS — all p95 SLAs met"
else
  echo "P3-GATE-13: FAIL — SLA violation (see ${EVIDENCE_FILE})"
  echo "  Note: NBA/consent p95 target ≤ 200ms; exam-start + campaign-create ≤ 3000ms"
  exit 1
fi
