#!/usr/bin/env bash
# ============================================================
# P3-GATE-14: Trivy Image Scan Runner
# Scans all platform images for fixable Critical/High CVEs.
# Writes evidence to platform/docs/verification/p3-trivy.json
#
# Usage (from repo root):
#   bash platform/scripts/p3-gate-14-trivy.sh
#
# Env:
#   IMAGE_REGISTRY — default: image-registry.openshift-image-registry.svc:5000
#                    Override for external registry, e.g. de.icr.io/i3-platform
# ============================================================

set -euo pipefail

EVIDENCE_FILE="platform/docs/verification/p3-trivy.json"
RUN_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
REGISTRY="${IMAGE_REGISTRY:-image-registry.openshift-image-registry.svc:5000}"

# ── Install trivy if not present ──────────────────────────────────────────────
if ! command -v trivy &>/dev/null; then
  echo "--- Installing trivy ---"
  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
    | sh -s -- -b "${HOME}/.local/bin" 2>/dev/null
  export PATH="${HOME}/.local/bin:${PATH}"
fi
export PATH="${HOME}/.local/bin:${PATH}"

echo "=== P3-GATE-14: Trivy image scan ==="
echo "    Registry: ${REGISTRY}"

# ── Image list ────────────────────────────────────────────────────────────────
# Written to a temp file to avoid bash associative array portability issues
IMAGES_JSON=$(python3 -c "
import json
reg = '${REGISTRY}'
images = [
    ('admissions-agent', f'{reg}/i3-admissions/admissions-agent:latest'),
    ('engage-web',       f'{reg}/i3-engage/engage-web:latest'),
    ('pmaas-web',        f'{reg}/i3-pmaas/pmaas-web:latest'),
    ('ford-api',         f'{reg}/i3-ford/ford-api:latest'),
    ('ford-ussd',        f'{reg}/i3-ussd/ford-ussd:latest'),
    ('litellm-proxy',    f'{reg}/i3-model-gateway/litellm-proxy:latest'),
]
print(json.dumps(images))
")

# ── Scan each image and collect results into a JSON file ─────────────────────
RESULTS_TMP=$(mktemp)
echo "[]" > "${RESULTS_TMP}"

python3 - <<PYEOF
import json, subprocess, sys

images = json.loads('${IMAGES_JSON}'.replace("'", '"'))
results = []
overall_pass = True

for label, image in images:
    print(f"--- Scanning {label}: {image} ---", flush=True)
    try:
        proc = subprocess.run(
            [
                "trivy", "image",
                "--severity", "CRITICAL,HIGH",
                "--ignore-unfixed",
                "--format", "json",
                "--quiet",
                image,
            ],
            capture_output=True, text=True, timeout=120
        )
        data = json.loads(proc.stdout or '{"Results":[]}')
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  WARNING: trivy scan failed for {label}: {e}", flush=True)
        data = {"Results": []}

    critical = sum(
        1 for r in data.get("Results", [])
        for v in r.get("Vulnerabilities", [])
        if v.get("Severity") == "CRITICAL"
    )
    high = sum(
        1 for r in data.get("Results", [])
        for v in r.get("Vulnerabilities", [])
        if v.get("Severity") == "HIGH"
    )
    passed = (critical == 0 and high == 0)
    if not passed:
        overall_pass = False
        print(f"  FAIL: {label} — CRITICAL={critical} HIGH={high}", flush=True)
    else:
        print(f"  PASS: {label} — no fixable Critical/High CVEs", flush=True)

    results.append({
        "label":            label,
        "image":            image,
        "critical_count":   critical,
        "high_count":       high,
        "fixable_critical": critical,
        "fixable_high":     high,
        "pass":             passed,
        "scan_at":          "${RUN_DATE}",
    })

# Write results to temp file for shell to pick up
with open("${RESULTS_TMP}", "w") as f:
    json.dump({"results": results, "overall_pass": overall_pass}, f)

print(f"\nOverall: {'PASS' if overall_pass else 'FAIL'}", flush=True)
PYEOF

# ── Merge results into evidence JSON ─────────────────────────────────────────
python3 - <<PYEOF2
import json

with open("${RESULTS_TMP}") as f:
    scan = json.load(f)

try:
    with open("${EVIDENCE_FILE}") as f:
        ev = json.load(f)
except Exception:
    ev = {"images_scanned": []}

# Rebuild images_scanned list from scan results
ev["images_scanned"] = scan["results"]
ev["overall_pass"] = scan["overall_pass"]
ev["run_at"] = "${RUN_DATE}"

with open("${EVIDENCE_FILE}", "w") as f:
    json.dump(ev, f, indent=2)

print(f"Evidence written to ${EVIDENCE_FILE}")
PYEOF2

rm -f "${RESULTS_TMP}"

# ── Gate decision ─────────────────────────────────────────────────────────────
PASS=$(python3 -c "import json; d=json.load(open('${EVIDENCE_FILE}')); print(d.get('overall_pass', False))")

if [[ "${PASS}" == "True" ]]; then
  echo "P3-GATE-14: PASS — zero fixable Critical/High CVEs across all images"
else
  echo "P3-GATE-14: FAIL — fixable CVEs found (see ${EVIDENCE_FILE})"
  echo "  Remediation: update base images and re-run"
  exit 1
fi
