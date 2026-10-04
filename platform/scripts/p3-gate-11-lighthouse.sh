#!/usr/bin/env bash
# ============================================================
# P3-GATE-11: Lighthouse PWA Score Runner
# Runs lhci against Engage and PMaaS staging, writes evidence JSON.
#
# Prerequisites:
#   npm install -g @lhci/cli@0.13
#   Staging must be reachable (Keycloak bypass or test user token)
#
# Usage: bash platform/scripts/p3-gate-11-lighthouse.sh
# ============================================================

set -euo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-lighthouse.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=== P3-GATE-11: Lighthouse PWA audit ==="

# ── Engage ────────────────────────────────────────────────────────────────────
echo "--- Running lhci for Engage ---"
ENGAGE_RESULT=$(lhci autorun \
  --config=platform/engage/web/lighthouserc.json \
  --collect.url=https://engage.i3technologies.co.ke/dashboard \
  --output=json 2>&1 || true)

# Parse scores from lhci JSON output (lhci writes JSON summary to stdout)
ENGAGE_PWA=$(echo "${ENGAGE_RESULT}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    runs = data.get('runs', [{}])
    scores = runs[0].get('summary', {})
    print(scores.get('categories.pwa', 'null'))
except:
    print('null')
" 2>/dev/null || echo "null")

echo "    Engage PWA score: ${ENGAGE_PWA}"

# ── PMaaS ─────────────────────────────────────────────────────────────────────
echo "--- Running lhci for PMaaS ---"
PMAAS_RESULT=$(lhci autorun \
  --config=platform/pmaas/web/lighthouserc.json \
  --collect.url=https://pmaas.i3technologies.co.ke/dashboard \
  --output=json 2>&1 || true)

PMAAS_PWA=$(echo "${PMAAS_RESULT}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    runs = data.get('runs', [{}])
    scores = runs[0].get('summary', {})
    print(scores.get('categories.pwa', 'null'))
except:
    print('null')
" 2>/dev/null || echo "null")

echo "    PMaaS PWA score: ${PMAAS_PWA}"

# ── Write evidence JSON ───────────────────────────────────────────────────────
python3 - <<PYEOF
import json, sys

with open("${EVIDENCE_FILE}") as f:
    ev = json.load(f)

engage_pwa  = ${ENGAGE_PWA}  if "${ENGAGE_PWA}"  != "null" else None
pmaas_pwa   = ${PMAAS_PWA}   if "${PMAAS_PWA}"   != "null" else None
threshold   = 0.80

ev["engage"]["scores"]["pwa"]  = engage_pwa
ev["engage"]["lhci_run_at"]    = "${RUN_DATE}"
ev["engage"]["pass"]           = (engage_pwa is not None and engage_pwa >= threshold)

ev["pmaas"]["scores"]["pwa"]   = pmaas_pwa
ev["pmaas"]["lhci_run_at"]     = "${RUN_DATE}"
ev["pmaas"]["pass"]            = (pmaas_pwa is not None and pmaas_pwa >= threshold)

ev["overall_pass"] = ev["engage"]["pass"] and ev["pmaas"]["pass"]

with open("${EVIDENCE_FILE}", "w") as f:
    json.dump(ev, f, indent=2)

print(json.dumps({"engage_pwa": engage_pwa, "pmaas_pwa": pmaas_pwa,
                  "threshold": threshold, "pass": ev["overall_pass"]}, indent=2))
PYEOF

# ── Gate decision ─────────────────────────────────────────────────────────────
PASS=$(python3 -c "import json; d=json.load(open('${EVIDENCE_FILE}')); print(d['overall_pass'])")

if [[ "${PASS}" == "True" ]]; then
  echo "P3-GATE-11: PASS — both apps PWA score >= 0.80"
else
  echo "P3-GATE-11: FAIL — one or more apps below PWA threshold"
  cat "${EVIDENCE_FILE}"
  exit 1
fi
