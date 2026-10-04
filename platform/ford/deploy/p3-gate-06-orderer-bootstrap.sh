#!/usr/bin/env bash
# ============================================================
# P3-GATE-06 Bootstrap Script — Orderer MSP + ford-channel Join
# Unblocks P3-GATE-06 and P3-GATE-07 (ford-channel + chaincode).
#
# Prerequisites:
#   IBM Cloud ROKS cluster — set IBMCLOUD_API_KEY or run ibmcloud login first.
#
# HC-2: Fabric staging must be live by November 2026
# HC-6: Chaincode only accepts HMAC tokens — never raw NIDs
# HC-8: voteChoicesCollection PDC enforces ballot secrecy
# ============================================================

set -euo pipefail

# ── Cluster auth (skipped if kubeconfig already set) ─────────────────────────
if ! kubectl cluster-info &>/dev/null 2>&1; then
  if [[ -n "${IBMCLOUD_API_KEY:-}" ]]; then
    echo "--- Authenticating to IBM Cloud ---"
    ibmcloud login --apikey "${IBMCLOUD_API_KEY}" -r eu-de -g i3-production --quiet
    ibmcloud ks cluster config --cluster i3-platform
  else
    echo "ERROR: kubectl not connected. Set IBMCLOUD_API_KEY or run:"
    echo "  ibmcloud login --sso && ibmcloud ks cluster config --cluster i3-platform"
    exit 1
  fi
fi

NS="i3-ford"
MANIFESTS_DIR="platform/ford/manifests"
DEPLOY_DIR="platform/ford/deploy"

echo "=== P3-GATE-06/07: Orderer MSP bootstrap + ford-channel join ==="

# Step 1: Enroll orderer MSP
echo "--- Step 1: Applying orderer-msp-enroll Job ---"
kubectl apply -f "${MANIFESTS_DIR}/orderer-msp-init-job.yaml" --validate=false
echo "    Waiting for orderer-msp-enroll Job (max 3 min)..."
kubectl wait --for=condition=complete job/orderer-msp-enroll \
  -n ${NS} --timeout=180s
kubectl get secret orderer-msp -n ${NS} -o jsonpath='{.metadata.name}'
echo " — orderer-msp Secret ready"

# Step 2: Patch orderer StatefulSet
echo "--- Step 2: Patching orderer StatefulSet ---"
kubectl patch statefulset orderer -n ${NS} \
  --patch-file "${MANIFESTS_DIR}/orderer-statefulset-patch.yaml" \
  --type=merge

# Step 3: Wait for orderer
echo "--- Step 3: Waiting for orderer pod (max 3 min) ---"
kubectl rollout status statefulset/orderer -n ${NS} --timeout=180s

# Step 4: Apply channel join Job
echo "--- Step 4: Applying ford-channel-join Job ---"
kubectl apply -f "${DEPLOY_DIR}/channel-join-job.yaml" --validate=false

echo "    Waiting for ford-channel-join (max 3 min)..."
kubectl wait --for=condition=complete job/ford-channel-join \
  -n ${NS} --timeout=180s
kubectl logs job/ford-channel-join -n ${NS} | tail -10

# Step 5: P3-GATE-06 sensor check
echo "--- Step 5: P3-GATE-06 sensor check ---"
CHANNEL_LIST=$(kubectl exec -n ${NS} peer0-i3tech -- \
  peer channel list 2>/dev/null || echo "")

if echo "${CHANNEL_LIST}" | grep -q "ford-channel"; then
  echo "P3-GATE-06: PASS — ford-channel listed"
else
  echo "P3-GATE-06: FAIL — ford-channel not found"
  echo "Output: ${CHANNEL_LIST}"
  exit 1
fi

# Step 6: Wait for chaincode deploy Job
echo "--- Step 6: Waiting for ford-chaincode-deploy Job (max 5 min) ---"
kubectl wait --for=condition=complete job/ford-chaincode-deploy \
  -n ${NS} --timeout=300s
kubectl logs job/ford-chaincode-deploy -n ${NS} | tail -15

# Step 7: P3-GATE-07 sensor check
echo "--- Step 7: P3-GATE-07 sensor check ---"
CC_LIST=$(kubectl exec -n ${NS} peer0-i3tech -- \
  peer chaincode list --instantiated -C ford-channel 2>/dev/null || echo "")

if echo "${CC_LIST}" | grep -q "membership-registry"; then
  echo "P3-GATE-07: PASS — membership-registry instantiated on ford-channel"
else
  echo "P3-GATE-07: FAIL — membership-registry not found"
  echo "Output: ${CC_LIST}"
  exit 1
fi

echo ""
echo "=== P3-GATE-06 + P3-GATE-07 complete ==="
