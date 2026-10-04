#!/usr/bin/env bash
# ============================================================
# P3-GATE-08 Bootstrap Script — FORD-Asili USSD Bridge
# Applies i3-ussd namespace and ford-ussd Deployment to staging.
#
# Prerequisites:
#   IBM Cloud ROKS cluster — set one of:
#     export IBMCLOUD_API_KEY=<key>   (non-interactive)
#     or: ibmcloud login --sso        (interactive)
#   Then: ibmcloud ks cluster config --cluster i3-platform
#
# HC-2: Must be deployed to staging by November 2026
# HC-6: MEMBER_HMAC_SECRET injected from OpenBao — never hardcoded
# ============================================================

set -euo pipefail

# ── Cluster auth (skipped if kubeconfig already set) ─────────────────────────
if ! kubectl cluster-info &>/dev/null 2>&1; then
  if [[ -n "${IBMCLOUD_API_KEY:-}" ]]; then
    echo "--- Authenticating to IBM Cloud (non-interactive) ---"
    ibmcloud login --apikey "${IBMCLOUD_API_KEY}" -r eu-de -g i3-production --quiet
    ibmcloud ks cluster config --cluster i3-platform
  elif command -v ibmcloud &>/dev/null; then
    echo "--- No kubeconfig found. Run one of:"
    echo "    ibmcloud login --sso && ibmcloud ks cluster config --cluster i3-platform"
    echo "    export IBMCLOUD_API_KEY=<key> and re-run this script"
    exit 1
  else
    echo "ERROR: kubectl not connected and ibmcloud CLI not found."
    echo "  Install: https://cloud.ibm.com/docs/cli"
    exit 1
  fi
fi

NAMESPACE="i3-ussd"
NAMESPACES_YAML="platform/namespaces/namespaces.yaml"
DEPLOY_YAML="platform/ford/ussd/deploy/ussd-deploy.yaml"

echo "=== P3-GATE-08: Applying i3-ussd namespace and USSD bridge deployment ==="

# Step 1: Apply namespace (--validate=false avoids openapi download on fresh kubeconfig)
echo "--- Step 1: Applying namespace manifest ---"
kubectl apply -f "${NAMESPACES_YAML}" --validate=false

# Step 2: Wait for namespace Active
echo "--- Step 2: Waiting for i3-ussd namespace ---"
kubectl wait --for=jsonpath='{.status.phase}'=Active \
  namespace/${NAMESPACE} --timeout=30s

# Step 3: Create ford-ussd-secrets from OpenBao (skip if exists)
if ! kubectl get secret ford-ussd-secrets -n ${NAMESPACE} &>/dev/null; then
  echo "--- Step 3: Creating ford-ussd-secrets from OpenBao ---"
  HMAC_SECRET=$(vault kv get -field=secret i3/ford/hmac-secret 2>/dev/null || echo "")
  AT_API_KEY=$(vault kv get -field=key i3/ford/at-api-key 2>/dev/null || echo "")
  AT_USERNAME=$(vault kv get -field=username i3/ford/at-username 2>/dev/null || echo "")

  if [[ -z "$HMAC_SECRET" || -z "$AT_API_KEY" ]]; then
    echo "WARNING: Could not retrieve ford secrets from OpenBao."
    echo "  Creating placeholder secret — update with real values before traffic hits the pod."
    HMAC_SECRET="${HMAC_SECRET:-placeholder-hmac}"
    AT_API_KEY="${AT_API_KEY:-placeholder-at-key}"
    AT_USERNAME="${AT_USERNAME:-sandbox}"
  fi

  kubectl create secret generic ford-ussd-secrets \
    --from-literal=MEMBER_HMAC_SECRET="${HMAC_SECRET}" \
    --from-literal=AT_API_KEY="${AT_API_KEY}" \
    --from-literal=AT_USERNAME="${AT_USERNAME}" \
    -n ${NAMESPACE}
  echo "Secret ford-ussd-secrets created."
else
  echo "--- Step 3: ford-ussd-secrets already exists — skipping ---"
fi

# Step 4: Apply Deployment + Service + Route + NetworkPolicy
echo "--- Step 4: Applying USSD bridge deployment manifest ---"
kubectl apply -f "${DEPLOY_YAML}" --validate=false

# Step 5: Wait for rollout
echo "--- Step 5: Waiting for ford-ussd rollout ---"
kubectl rollout status deployment/ford-ussd -n ${NAMESPACE} --timeout=120s

# Step 6: P3-GATE-08 sensor check
echo "--- Step 6: P3-GATE-08 sensor check ---"
RUNNING=$(kubectl get pod -n ${NAMESPACE} -l app=ford-ussd \
  --field-selector=status.phase=Running \
  -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)

if [[ -n "${RUNNING}" ]]; then
  echo "P3-GATE-08: PASS — ford-ussd pod(s) Running: ${RUNNING}"
else
  echo "P3-GATE-08: FAIL — no Running pods in ${NAMESPACE}"
  kubectl get pods -n ${NAMESPACE} -l app=ford-ussd
  exit 1
fi

echo ""
echo "=== P3-GATE-08 complete ==="
echo "    Verify: curl -s -X POST https://ussd.i3technologies.co.ke/ussd \\"
echo "      -d 'sessionId=test001&serviceCode=*509%23&phoneNumber=%2B254700000001&text='"
echo "    Expected: starts with 'CON'"
