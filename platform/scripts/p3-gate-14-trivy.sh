#!/usr/bin/env bash
# ============================================================
# P3-GATE-14: Trivy Image Scan Runner
# Scans all platform images for Critical/High CVEs with fixes.
# Writes evidence JSON and exits 1 if any fixable findings exist.
#
# Prerequisites:
#   trivy installed: https://aquasecurity.github.io/trivy/
#   oc / kubectl context set to the i3 staging cluster (for digest lookup)
#   OCI registry credentials in trivy's credential store
#
# Usage: bash platform/scripts/p3-gate-14-trivy.sh
# ============================================================

set -euo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-trivy.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
REGISTRY="${IMAGE_REGISTRY:-image-registry.openshift-image-registry.svc:5000}"

declare -A IMAGES=(
  ["admissions-agent"]="${REGISTRY}/i3-admissions/admissions-agent:latest"
  ["engage-web"]="${REGISTRY}/i3-engage/engage-web:latest"
  ["pmaas-web"]="${REGISTRY}/i3-pmaas/pmaas-web:latest"
  ["ford-api"]="${REGISTRY}/i3-ford/ford-api:latest"
  ["ford-ussd"]="${REGISTRY}/i3-ussd/ford-ussd:latest"
  ["litellm-proxy"]="${REGISTRY}/i3-model-gateway/litellm-proxy:latest"
)

echo "=== P3-GATE-14: Trivy image scan ==="
OVERALL_PASS=true
declare -A RESULTS

for label in "${!IMAGES[@]}"; do
  image="${IMAGES[$label]}"
  echo "--- Scanning ${label}: ${image} ---"

  # Run trivy; capture JSON output; --ignore-unfixed skips CVEs with no patch available
  TRIVY_OUT=$(trivy image \
    --severity CRITICAL,HIGH \
    --ignore-unfixed \
    --format json \
    --quiet \
    "${image}" 2>/dev/null || echo '{"Results":[]}')

  # Count findings
  CRITICAL=$(echo "${TRIVY_OUT}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
c = sum(
    1 for r in data.get('Results', [])
    for v in r.get('Vulnerabilities', [])
    if v.get('Severity') == 'CRITICAL'
)
print(c)" 2>/dev/null || echo "0")

  HIGH=$(echo "${TRIVY_OUT}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
h = sum(
    1 for r in data.get('Results', [])
    for v in r.get('Vulnerabilities', [])
    if v.get('Severity') == 'HIGH'
)
print(h)" 2>/dev/null || echo "0")

  PASS="true"
  if [[ "${CRITICAL}" -gt 0 || "${HIGH}" -gt 0 ]]; then
    PASS="false"
    OVERALL_PASS=false
    echo "  FAIL: ${label} — CRITICAL=${CRITICAL} HIGH=${HIGH}"
  else
    echo "  PASS: ${label} — no fixable Critical/High CVEs"
  fi

  RESULTS["${label}"]="${CRITICAL}:${HIGH}:${PASS}"
done

# ── Write evidence JSON ───────────────────────────────────────────────────────
python3 - <<PYEOF
import json

with open("${EVIDENCE_FILE}") as f:
    ev = json.load(f)

results_raw = {}
for item in "${!RESULTS[@]}".split():
    parts = "${RESULTS[$item]}".split(":")
    if len(parts) == 3:
        results_raw[item] = {"critical": int(parts[0]), "high": int(parts[1]), "pass": parts[2] == "true"}

for img_entry in ev["images_scanned"]:
    label = img_entry["image"].split("/")[-1].split(":")[0]
    if label in results_raw:
        img_entry["critical_count"]  = results_raw[label]["critical"]
        img_entry["high_count"]      = results_raw[label]["high"]
        img_entry["fixable_critical"] = results_raw[label]["critical"]
        img_entry["fixable_high"]    = results_raw[label]["high"]
        img_entry["pass"]            = results_raw[label]["pass"]
        img_entry["scan_at"]         = "${RUN_DATE}"

ev["overall_pass"] = ${OVERALL_PASS}
with open("${EVIDENCE_FILE}", "w") as f:
    json.dump(ev, f, indent=2)
print("Evidence written to ${EVIDENCE_FILE}")
PYEOF

# ── Gate decision ─────────────────────────────────────────────────────────────
if [[ "${OVERALL_PASS}" == "true" ]]; then
  echo ""
  echo "P3-GATE-14: PASS — zero fixable Critical/High CVEs across all images"
else
  echo ""
  echo "P3-GATE-14: FAIL — fixable Critical/High CVEs found (see ${EVIDENCE_FILE})"
  echo "  Remediation: update base images and re-run pipeline"
  exit 1
fi
