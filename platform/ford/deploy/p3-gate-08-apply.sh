#!/usr/bin/env bash
# ============================================================
# P3-GATE-08 Bootstrap Script — FORD-Asili USSD Bridge
# Applies i3-ussd namespace and ford-ussd Deployment to staging.
#
# Prerequisites:
#   - oc / kubectl context set to the i3 staging cluster
#   - ford-ussd-secrets Secret must exist in i3-ussd before pods start:
#       oc create secret generic ford-ussd-secrets \
#         --from-literal=MEMBER_HMAC_SECRET=$(vault kv get -field=secret i3/ford/hmac-secret) \
#         --from-literal=AT_API_KEY=$(vault kv get -field=key i3/ford/at-api-key) \
#         --from-literal=AT_USERNAME=$(vault kv get -field=username i3/ford/at-username) \
#         -n i3-ussd
#
# Sensor check after apply:
#   kubectl get pod -n i3-ussd -l app=ford-ussd
#   # Expected: Running 1/1
#
# HC-2: Must be deployed to staging by November 2026
# HC-6: MEMBER_HMAC_SECRET injected from OpenBao — never hardcoded
# ============================================================

set -euo pipefail

NAMESPACE="i3-ussd"
NAMESPACES_YAML="platform/namespaces/namespaces.yaml"
DEPLOY_YAML="platform/ford/ussd/deploy/ussd-deploy.yaml"

echo "=== P3-GATE-08: Applying i3-ussd namespace and USSD bridge deployment ==="

# Step 1: Ensure namespace exists (idempotent — apply all platform namespaces)
echo "--- Step 1: Applying namespace manifest ---"
kubectl apply -f "${NAMESPACES_YAML}"

# Step 2: Wait for namespace to be Active
echo "--- Step 2: Waiting for i3-ussd namespace to be Active ---"
kubectl wait --for=jsonpath='{.status.phase}'=Active \
  namespace/${NAMESPACE} --timeout=30s

# Step 3: Create ford-ussd-secrets from OpenBao (skip if already exists)
if ! kubectl get secret ford-ussd-secrets -n ${NAMESPACE} &>/dev/null; then
  echo "--- Step 3: Creating ford-ussd-secrets from OpenBao ---"
  # HC-6: secrets sourced from OpenBao KV v2, never hardcoded
  HMAC_SECRET=$(vault kv get -field=secret i3/ford/hmac-secret 2>/dev/null || echo "")
  AT_API_KEY=$(vault kv get -field=key i3/ford/at-api-key 2>/dev/null || echo "")
  AT_USERNAME=$(vault kv get -field=username i3/ford/at-username 2>/dev/null || echo "")

  if [[ -z "$HMAC_SECRET" || -z "$AT_API_KEY" ]]; then
    echo "ERROR: Could not retrieve ford secrets from OpenBao."
    echo "       Ensure OpenBao is unsealed and i3/ford/* paths are populated."
    echo "       Manually run: vault kv put i3/ford/hmac-secret secret=<256-bit-hex>"
    exit 1
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

# Step 4: Apply USSD bridge Deployment + Service + Route + NetworkPolicy
echo "--- Step 4: Applying USSD bridge deployment manifest ---"
kubectl apply -f "${DEPLOY_YAML}"

# Step 5: Wait for rollout
echo "--- Step 5: Waiting for ford-ussd rollout to complete ---"
kubectl rollout status deployment/ford-ussd -n ${NAMESPACE} --timeout=120s

# Step 6: Sensor check (P3-GATE-08)
echo "--- Step 6: P3-GATE-08 sensor check ---"
RUNNING=$(kubectl get pod -n ${NAMESPACE} -l app=ford-ussd \
  --field-selector=status.phase=Running \
  -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)

if [[ -n "${RUNNING}" ]]; then
  echo "P3-GATE-08: PASS — ford-ussd pod(s) Running: ${RUNNING}"
else
  echo "P3-GATE-08: FAIL — no Running pods found in ${NAMESPACE}"
  kubectl get pods -n ${NAMESPACE} -l app=ford-ussd
  exit 1
fi

echo ""
echo "=== P3-GATE-08 bootstrap complete ==="
echo "    Verify USSD endpoint: curl -s -X POST https://ussd.i3technologies.co.ke/ussd \\"
echo "      -d 'sessionId=test001&serviceCode=*509%23&phoneNumber=%2B254700000001&text='"
echo "    Expected: response starts with 'CON'"
