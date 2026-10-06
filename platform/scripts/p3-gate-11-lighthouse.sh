#!/usr/bin/env bash
# ============================================================
# P3-GATE-11: Lighthouse PWA Score Runner
# Installs lhci if needed, runs audits against Engage and PMaaS staging,
# writes evidence to platform/docs/verification/p3-lighthouse.json
#
# Usage (from repo root):
#   bash platform/scripts/p3-gate-11-lighthouse.sh
#
# Env vars:
#   ENGAGE_URL   — default: https://engage.i3technologies.co.ke/dashboard
#   PMAAS_URL    — default: https://pmaas.i3technologies.co.ke/dashboard
# ============================================================

set -uo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-lighthouse.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
THRESHOLD=0.80

# ── Helper: write evidence JSON and emit gate decision ────────────────────────
write_evidence_and_gate() {
    # All inputs come via environment variables to avoid heredoc interpolation bugs:
    # EVIDENCE_FILE, RUN_DATE, THRESHOLD, ENGAGE_PWA, PMAAS_PWA
    export EVIDENCE_FILE RUN_DATE THRESHOLD ENGAGE_PWA PMAAS_PWA
    python3 - <<'PYEOF'
import json, os, sys

evidence_file = os.environ["EVIDENCE_FILE"]
run_date      = os.environ["RUN_DATE"]
threshold     = float(os.environ["THRESHOLD"])
engage_raw    = os.environ.get("ENGAGE_PWA", "null")
pmaas_raw     = os.environ.get("PMAAS_PWA",  "null")

def parse_score(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

engage_pwa = parse_score(engage_raw)
pmaas_pwa  = parse_score(pmaas_raw)

try:
    with open(evidence_file) as f:
        ev = json.load(f)
except Exception:
    ev = {"engage": {}, "pmaas": {}}

ev["engage"]["scores"]      = {"pwa": engage_pwa}
ev["engage"]["lhci_run_at"] = run_date
ev["engage"]["pass"]        = engage_pwa is not None and engage_pwa >= threshold

ev["pmaas"]["scores"]      = {"pwa": pmaas_pwa}
ev["pmaas"]["lhci_run_at"] = run_date
ev["pmaas"]["pass"]        = pmaas_pwa is not None and pmaas_pwa >= threshold

ev["overall_pass"] = ev["engage"]["pass"] and ev["pmaas"]["pass"]

with open(evidence_file, "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({
    "engage_pwa": engage_pwa,
    "pmaas_pwa":  pmaas_pwa,
    "threshold":  threshold,
    "pass":       ev["overall_pass"],
}, indent=2))

if ev["overall_pass"]:
    print("P3-GATE-11: PASS — both apps PWA score >= " + str(threshold))
else:
    print("P3-GATE-11: FAIL — one or more apps below PWA threshold " + str(threshold))
    print("  Evidence: " + evidence_file)
    print("  Manual check: curl -s https://engage.i3technologies.co.ke/sw.js | head -1")
    sys.exit(1)
PYEOF
}

# ── Helper: skip gracefully when infra is unavailable ─────────────────────────
skip_gate() {
    local reason="$1"
    echo "P3-GATE-11: SKIPPED — ${reason}"
    echo "  Run via Tekton pipeline against staging cluster to produce real scores."
    ENGAGE_PWA="null"
    PMAAS_PWA="null"
    export EVIDENCE_FILE RUN_DATE THRESHOLD ENGAGE_PWA PMAAS_PWA
    python3 - <<'PYEOF'
import json, os

evidence_file = os.environ["EVIDENCE_FILE"]
run_date      = os.environ["RUN_DATE"]

try:
    with open(evidence_file) as f:
        ev = json.load(f)
except Exception:
    ev = {"engage": {}, "pmaas": {}}

for app in ("engage", "pmaas"):
    ev[app].setdefault("scores", {})["pwa"] = None
    ev[app]["lhci_run_at"] = run_date
    ev[app]["pass"]        = False
    ev[app]["note"]        = os.environ.get("SKIP_REASON", "infra unavailable locally")

ev["overall_pass"] = False
ev["note"]         = "Pending live Tekton run"

with open(evidence_file, "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({"status": "SKIPPED", "evidence": evidence_file}))
PYEOF
    # SKIPPED is not a hard failure — Tekton will produce the real gate result
    exit 0
}

# ── Resolve node ──────────────────────────────────────────────────────────────
# In WSL, Windows npm/node shims exist on PATH but are NOT executable by WSL bash.
# Detect this by actually trying to run node, not just testing if the path exists.
NODE_OK=false
if command -v node &>/dev/null 2>&1; then
    if node --version &>/dev/null 2>&1; then
        NODE_OK=true
    fi
fi

if [[ "${NODE_OK}" == "false" ]]; then
    export SKIP_REASON="node not available in this shell (WSL: install via nodesource, or run via Tekton)"
    skip_gate "node not found or not executable"
fi

# ── Install lhci if not present or not executable ─────────────────────────────
LHCI_BIN=""
if command -v lhci &>/dev/null 2>&1; then
    if lhci --version &>/dev/null 2>&1; then
        LHCI_BIN=$(command -v lhci)
    fi
fi

if [[ -z "${LHCI_BIN}" ]]; then
    echo "--- Installing @lhci/cli via npm ---"
    npm install -g @lhci/cli@0.13 --silent 2>&1 || true
    if command -v lhci &>/dev/null 2>&1 && lhci --version &>/dev/null 2>&1; then
        LHCI_BIN=$(command -v lhci)
    fi
fi

if [[ -z "${LHCI_BIN}" ]]; then
    export SKIP_REASON="lhci could not be installed or is not executable"
    skip_gate "lhci not executable"
fi

# ── Run Lighthouse for both apps ──────────────────────────────────────────────
mkdir -p .lighthouseci

ENGAGE_URL="${ENGAGE_URL:-https://engage.i3technologies.co.ke/dashboard}"
PMAAS_URL="${PMAAS_URL:-https://pmaas.i3technologies.co.ke/dashboard}"

run_lighthouse() {
    local label="$1"
    local url="$2"

    echo "--- Running lhci for ${label}: ${url} ---"

    # Run lhci; ignore non-zero exit (score-below-threshold is expected during dev)
    "${LHCI_BIN}" autorun \
        --collect.url="${url}" \
        --collect.numberOfRuns=1 \
        --assert.assertions.categories:pwa="['error',{'minScore':${THRESHOLD}}]" \
        --assert.assertions.service-worker="['error',{'minScore':1}]" \
        --assert.assertions.installable-manifest="['error',{'minScore':1}]" \
        --output=json >/dev/null 2>&1 || true

    # Find the most recently written lhci report
    local lhr_json
    lhr_json=$(find .lighthouseci -name "lhr-*.json" 2>/dev/null \
               | sort | tail -1 || echo "")

    local pwa_score="null"
    if [[ -n "${lhr_json}" && -f "${lhr_json}" ]]; then
        pwa_score=$(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(d['categories']['pwa']['score'])
except Exception:
    print('null')
" "${lhr_json}" 2>/dev/null || echo "null")
    fi

    # Echo ONLY the score — no other text — so the caller captures a clean value
    echo "${pwa_score}"
}

ENGAGE_PWA=$(run_lighthouse "Engage" "${ENGAGE_URL}")
echo "    Engage PWA score: ${ENGAGE_PWA}"

PMAAS_PWA=$(run_lighthouse "PMaaS" "${PMAAS_URL}")
echo "    PMaaS PWA score: ${PMAAS_PWA}"

# ── Write evidence + gate decision (via Python, reading from env vars) ─────────
write_evidence_and_gate
