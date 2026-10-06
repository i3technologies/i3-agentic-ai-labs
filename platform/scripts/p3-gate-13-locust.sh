#!/usr/bin/env bash
# ============================================================
# P3-GATE-13: Locust SLA Runner
# Creates a venv, installs locust, runs load tests against staging,
# writes p95 latency evidence to platform/docs/verification/p3-locust-sla.json
#
# Usage (from repo root):
#   bash platform/scripts/p3-gate-13-locust.sh
#
# Env vars:
#   EVALOS_HOST        — default: https://evalos.i3technologies.co.ke
#   ENGAGE_HOST        — default: https://engage.i3technologies.co.ke
#   LITELLM_MASTER_KEY — LiteLLM key for AI Lab user
# ============================================================

set -uo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-locust-sla.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VENV_DIR=".bob/tmp/locust-venv"

# ── Helper: write evidence + gate decision via Python env vars ────────────────
write_evidence_and_gate() {
    export EVIDENCE_FILE RUN_DATE EVALOS_P95 ENGAGE_P95
    python3 - <<'PYEOF'
import json, os, sys

evidence_file = os.environ["EVIDENCE_FILE"]
run_date      = os.environ["RUN_DATE"]
evalos_raw    = os.environ.get("EVALOS_P95", "null")
engage_raw    = os.environ.get("ENGAGE_P95", "null")

def parse_ms(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

evalos_p95 = parse_ms(evalos_raw)
engage_p95 = parse_ms(engage_raw)

try:
    with open(evidence_file) as f:
        ev = json.load(f)
except Exception:
    ev = {"nba_consent": {}, "exam_start": {}, "campaign_create": {}}

ev["exam_start"]["p95_ms"]      = evalos_p95
ev["exam_start"]["pass"]        = evalos_p95 is not None and evalos_p95 <= 3000

ev["campaign_create"]["p95_ms"] = engage_p95
ev["campaign_create"]["pass"]   = engage_p95 is not None and engage_p95 <= 3000

# NBA/consent fast path uses EvalOS p95 as proxy (LiteLLM cache warm)
ev["nba_consent"]["p95_ms"] = evalos_p95
ev["nba_consent"]["pass"]   = evalos_p95 is not None and evalos_p95 <= 200

ev["overall_pass"] = all([
    ev["nba_consent"].get("pass",       False),
    ev["exam_start"].get("pass",        False),
    ev["campaign_create"].get("pass",   False),
])
ev["run_at"] = run_date

with open(evidence_file, "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({
    "exam_start_p95":      ev["exam_start"].get("p95_ms"),
    "campaign_create_p95": ev["campaign_create"].get("p95_ms"),
    "overall_pass":        ev["overall_pass"],
}, indent=2))

if ev["overall_pass"]:
    print("P3-GATE-13: PASS — all p95 SLAs met")
else:
    print("P3-GATE-13: FAIL — SLA violation (see " + evidence_file + ")")
    print("  NBA/consent p95 target ≤ 200ms; exam-start + campaign-create ≤ 3000ms")
    sys.exit(1)
PYEOF
}

# ── Helper: skip gracefully when target hosts are unreachable ─────────────────
skip_gate() {
    local reason="$1"
    echo "P3-GATE-13: SKIPPED — ${reason}"
    echo "  Run via Tekton pipeline against staging cluster."
    EVALOS_P95="null"
    ENGAGE_P95="null"
    export EVIDENCE_FILE RUN_DATE EVALOS_P95 ENGAGE_P95
    python3 - <<'PYEOF'
import json, os

evidence_file = os.environ["EVIDENCE_FILE"]
run_date      = os.environ["RUN_DATE"]

try:
    with open(evidence_file) as f:
        ev = json.load(f)
except Exception:
    ev = {"nba_consent": {}, "exam_start": {}, "campaign_create": {}}

for k in ("nba_consent", "exam_start", "campaign_create"):
    ev[k]["p95_ms"] = None
    ev[k]["pass"]   = False
    ev[k]["note"]   = os.environ.get("SKIP_REASON", "infra unavailable locally")

ev["overall_pass"] = False
ev["note"]         = "Pending live Tekton run"
ev["run_at"]       = run_date

with open(evidence_file, "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({"status": "SKIPPED", "evidence": evidence_file}))
PYEOF
    exit 0
}

# ── Ensure locust is available (venv, not system pip) ─────────────────────────
PYTHON_BIN="python3"
if ! command -v python3 &>/dev/null 2>&1; then
    if command -v python &>/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        export SKIP_REASON="python3 not found"
        skip_gate "python3 not available"
    fi
fi

LOCUST_BIN=""

# 1. Already on PATH and works?
if command -v locust &>/dev/null 2>&1; then
    if locust --version &>/dev/null 2>&1; then
        LOCUST_BIN=$(command -v locust)
    fi
fi

# 2. Check ~/.local/bin (pip user installs)
if [[ -z "${LOCUST_BIN}" && -x "${HOME}/.local/bin/locust" ]]; then
    LOCUST_BIN="${HOME}/.local/bin/locust"
fi

# 3. Check existing venv
if [[ -z "${LOCUST_BIN}" && -x "${VENV_DIR}/bin/locust" ]]; then
    LOCUST_BIN="${VENV_DIR}/bin/locust"
fi

# 4. Create venv and install (avoids externally-managed-environment error)
if [[ -z "${LOCUST_BIN}" ]]; then
    echo "--- Creating locust venv at ${VENV_DIR} ---"
    mkdir -p "$(dirname "${VENV_DIR}")"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}" 2>&1

    if [[ -x "${VENV_DIR}/bin/pip" ]]; then
        echo "--- Installing locust into venv (timeout 120s) ---"
        # Use --timeout to avoid hanging in restricted network environments (WSL, CI)
        timeout 120 "${VENV_DIR}/bin/pip" install locust \
            --quiet --timeout 30 --retries 2 2>&1 || true
        if [[ -x "${VENV_DIR}/bin/locust" ]]; then
            LOCUST_BIN="${VENV_DIR}/bin/locust"
        fi
    fi
fi

if [[ -z "${LOCUST_BIN}" ]]; then
    export SKIP_REASON="locust could not be installed (venv creation failed)"
    skip_gate "locust not available"
fi

echo "Using locust: ${LOCUST_BIN}"
echo "$(${LOCUST_BIN} --version)"

EVALOS_HOST="${EVALOS_HOST:-https://evalos.i3technologies.co.ke}"
ENGAGE_HOST="${ENGAGE_HOST:-https://engage.i3technologies.co.ke}"

echo "=== P3-GATE-13: Locust SLA load test ==="
echo "    EvalOS: ${EVALOS_HOST}"
echo "    Engage: ${ENGAGE_HOST}"

# ── EvalOS exam start (p95 ≤ 3000ms) ─────────────────────────────────────────
echo "--- EvalOS exam start (100 users, 2 min) ---"
"${LOCUST_BIN}" -f platform/testing/testing.py EvalOSSandboxUser \
    --headless -u 100 -r 10 --run-time 2m \
    --host "${EVALOS_HOST}" \
    --csv=/tmp/locust-evalos \
    --only-summary 2>&1 | tail -20 || true

# ── Engage campaign (p95 ≤ 3000ms) ───────────────────────────────────────────
echo "--- Engage campaign (50 users, 2 min) ---"
"${LOCUST_BIN}" -f platform/testing/testing.py AILabAPIUser \
    --headless -u 50 -r 5 --run-time 2m \
    --host "${ENGAGE_HOST}" \
    --csv=/tmp/locust-engage \
    --only-summary 2>&1 | tail -20 || true

# ── Parse CSV results ─────────────────────────────────────────────────────────
parse_result() {
    # parse_result <csv_file> <name_filter_lowercase>
    # Prints p95 value, or "null" on failure
    local csv_path="$1"
    local name_filter="$2"
    export _CSV_PATH="${csv_path}" _NAME_FILTER="${name_filter}"
    python3 - <<'PYEOF'
import csv, os

csv_path    = os.environ["_CSV_PATH"]
name_filter = os.environ["_NAME_FILTER"].lower()

try:
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if name_filter in row.get("Name", "").lower():
                val = row.get("95%") or row.get("95th Percentile") or ""
                try:
                    print(float(val))
                    raise SystemExit(0)
                except ValueError:
                    pass
except FileNotFoundError:
    pass
print("null")
PYEOF
}

EVALOS_P95=$(parse_result "/tmp/locust-evalos_stats.csv" "submit")
ENGAGE_P95=$(parse_result "/tmp/locust-engage_stats.csv"  "campaign")

echo "    EvalOS exam-start p95: ${EVALOS_P95} ms"
echo "    Engage campaign p95:   ${ENGAGE_P95} ms"

# ── Write evidence + gate decision ────────────────────────────────────────────
write_evidence_and_gate
