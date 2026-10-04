#!/usr/bin/env bash
# ============================================================
# P3-GATE-11: Lighthouse PWA Score Runner
# Installs lhci if needed, runs audits against Engage and PMaaS staging,
# writes evidence to platform/docs/verification/p3-lighthouse.json
#
# Usage (from repo root):
#   bash platform/scripts/p3-gate-11-lighthouse.sh
# ============================================================

set -euo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-lighthouse.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
THRESHOLD=0.80

# ── Install lhci if not present ───────────────────────────────────────────────
if ! command -v lhci &>/dev/null; then
  echo "--- Installing @lhci/cli ---"
  npm install -g @lhci/cli@0.13 --silent
fi

run_lighthouse() {
  local label="$1"
  local url="$2"
  local config="$3"

  echo "--- Running lhci for ${label}: ${url} ---"

  # Run lhci and capture output; continue even if lhci exits non-zero (score below threshold)
  local tmpout
  tmpout=$(mktemp)

  lhci autorun \
    --collect.url="${url}" \
    --collect.numberOfRuns=1 \
    --assert.assertions.categories:pwa="['error',{'minScore':${THRESHOLD}}]" \
    --assert.assertions.service-worker="['error',{'minScore':1}]" \
    --assert.assertions.installable-manifest="['error',{'minScore':1}]" \
    --output=json 2>&1 | tee "${tmpout}" || true

  # Try to extract PWA score from lhci JSON summary (lhci writes a summary JSON)
  local lhr_json
  lhr_json=$(find .lighthouseci -name "*.json" -newer "${tmpout}" 2>/dev/null | head -1 || echo "")

  local pwa_score="null"
  if [[ -n "${lhr_json}" && -f "${lhr_json}" ]]; then
    pwa_score=$(python3 -c "
import json, sys
try:
    d = json.load(open('${lhr_json}'))
    print(d['categories']['pwa']['score'])
except:
    print('null')
" 2>/dev/null || echo "null")
  fi

  rm -f "${tmpout}"
  echo "${pwa_score}"
}

# ── Run Lighthouse for both apps ──────────────────────────────────────────────
mkdir -p .lighthouseci

ENGAGE_URL="${ENGAGE_URL:-https://engage.i3technologies.co.ke/dashboard}"
PMAAS_URL="${PMAAS_URL:-https://pmaas.i3technologies.co.ke/dashboard}"

ENGAGE_PWA=$(run_lighthouse "Engage" "${ENGAGE_URL}" "platform/engage/web/lighthouserc.json")
echo "    Engage PWA score: ${ENGAGE_PWA}"

PMAAS_PWA=$(run_lighthouse "PMaaS" "${PMAAS_URL}" "platform/pmaas/web/lighthouserc.json")
echo "    PMaaS PWA score: ${PMAAS_PWA}"

# ── Write evidence JSON ───────────────────────────────────────────────────────
python3 - <<PYEOF
import json

evidence_file = "${EVIDENCE_FILE}"
run_date = "${RUN_DATE}"
threshold = ${THRESHOLD}

engage_pwa_raw = "${ENGAGE_PWA}"
pmaas_pwa_raw  = "${PMAAS_PWA}"

def parse_score(s):
    try:
        v = float(s)
        return v
    except (ValueError, TypeError):
        return None

engage_pwa = parse_score(engage_pwa_raw)
pmaas_pwa  = parse_score(pmaas_pwa_raw)

try:
    with open(evidence_file) as f:
        ev = json.load(f)
except Exception:
    ev = {"engage": {}, "pmaas": {}}

ev["engage"]["scores"] = {"pwa": engage_pwa}
ev["engage"]["lhci_run_at"] = run_date
ev["engage"]["pass"] = engage_pwa is not None and engage_pwa >= threshold

ev["pmaas"]["scores"] = {"pwa": pmaas_pwa}
ev["pmaas"]["lhci_run_at"] = run_date
ev["pmaas"]["pass"] = pmaas_pwa is not None and pmaas_pwa >= threshold

ev["overall_pass"] = ev["engage"]["pass"] and ev["pmaas"]["pass"]

with open(evidence_file, "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({
    "engage_pwa": engage_pwa,
    "pmaas_pwa":  pmaas_pwa,
    "threshold":  threshold,
    "pass":       ev["overall_pass"]
}, indent=2))
PYEOF

# ── Gate decision ─────────────────────────────────────────────────────────────
PASS=$(python3 -c "import json; d=json.load(open('${EVIDENCE_FILE}')); print(d.get('overall_pass', False))")

if [[ "${PASS}" == "True" ]]; then
  echo "P3-GATE-11: PASS — both apps PWA score >= ${THRESHOLD}"
else
  echo "P3-GATE-11: FAIL — one or more apps below PWA threshold ${THRESHOLD}"
  echo "  Evidence: ${EVIDENCE_FILE}"
  echo "  Note: Ensure staging is reachable and service worker is registered."
  echo "  Manual check: curl -s https://engage.i3technologies.co.ke/sw.js | head -1"
  exit 1
fi
