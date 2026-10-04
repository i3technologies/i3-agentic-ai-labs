#!/usr/bin/env bash
# ============================================================
# P3-GATE-06 Bootstrap Script — Orderer MSP + ford-channel Join
# Unblocks P3-GATE-06 and P3-GATE-07 (ford-channel + chaincode).
#
# Sequential steps:
#   1. Apply orderer MSP enroll Job          (orderer-msp-init-job.yaml)
#   2. Patch orderer StatefulSet              (orderer-statefulset-patch.yaml)
#   3. Wait for orderer to be Running
#   4. Apply channel join Job                 (channel-join-job.yaml)
#   5. Wait for channel join to complete
#   6. Apply chaincode deploy Job             (channel-join-job.yaml — second resource)
#   7. Wait for chaincode deploy to complete
#   8. Sensor checks P3-GATE-06 + P3-GATE-07
#
# HC-2: Fabric staging must be live by November 2026
# HC-6: Chaincode only accepts HMAC tokens — never raw NIDs
# HC-8: voteChoicesCollection PDC enforces ballot secrecy
# ============================================================

set -euo pipefail

NS="i3-ford"
MANIFESTS_DIR="platform/ford/manifests"
DEPLOY_DIR="platform/ford/deploy"

echo "=== P3-GATE-06/07: Orderer MSP bootstrap + ford-channel join ==="

# ── Step 1: Enroll orderer MSP against ford-ca ────────────────────────────────
echo "--- Step 1: Applying orderer-msp-enroll Job ---"
kubectl apply -f "${MANIFESTS_DIR}/orderer-msp-init-job.yaml"
echo "    Waiting for orderer-msp-enroll Job to complete (max 3 min)..."
kubectl wait --for=condition=complete job/orderer-msp-enroll \
  -n ${NS} --timeout=180s
echo "    orderer-msp Secret created:"
kubectl get secret orderer-msp -n ${NS} -o jsonpath='{.metadata.name}'
echo ""

# ── Step 2: Patch orderer StatefulSet with MSP Secret mounts ─────────────────
echo "--- Step 2: Patching orderer StatefulSet with MSP volume mounts ---"
kubectl patch statefulset orderer -n ${NS} \
  --patch-file "${MANIFESTS_DIR}/orderer-statefulset-patch.yaml" \
  --type=merge

# ── Step 3: Wait for orderer pod to become Running ────────────────────────────
echo "--- Step 3: Waiting for orderer pod to be Running (max 3 min) ---"
kubectl rollout status statefulset/orderer -n ${NS} --timeout=180s

ORDERER_POD=$(kubectl get pod -n ${NS} -l app=orderer \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [[ -z "${ORDERER_POD}" ]]; then
  echo "ERROR: Orderer pod not found — check StatefulSet status"
  kubectl get pods -n ${NS} -l app=orderer
  exit 1
fi
echo "    Orderer pod ready: ${ORDERER_POD}"

# ── Step 4: Apply channel join Job ───────────────────────────────────────────
echo "--- Step 4: Applying ford-channel-join Job ---"
# channel-join-job.yaml contains both ford-channel-join and ford-chaincode-deploy Jobs
kubectl apply -f "${DEPLOY_DIR}/channel-join-job.yaml"

echo "    Waiting for ford-channel-join to complete (max 3 min)..."
kubectl wait --for=condition=complete job/ford-channel-join \
  -n ${NS} --timeout=180s

echo "    ford-channel-join logs:"
kubectl logs job/ford-channel-join -n ${NS} | tail -10

# ── Step 5: Sensor check P3-GATE-06 ─────────────────────────────────────────
echo "--- Step 5: P3-GATE-06 sensor check ---"
CHANNEL_LIST=$(kubectl exec -n ${NS} peer0-i3tech -- \
  peer channel list 2>/dev/null || echo "")

if echo "${CHANNEL_LIST}" | grep -q "ford-channel"; then
  echo "P3-GATE-06: PASS — ford-channel listed in peer channel list"
else
  echo "P3-GATE-06: FAIL — ford-channel not found"
  echo "Channel list output: ${CHANNEL_LIST}"
  exit 1
fi

# ── Step 6: Chaincode deploy Job ─────────────────────────────────────────────
echo "--- Step 6: Waiting for ford-chaincode-deploy Job to complete (max 5 min) ---"
kubectl wait --for=condition=complete job/ford-chaincode-deploy \
  -n ${NS} --timeout=300s

echo "    ford-chaincode-deploy logs:"
kubectl logs job/ford-chaincode-deploy -n ${NS} | tail -15

# ── Step 7: Sensor check P3-GATE-07 ─────────────────────────────────────────
echo "--- Step 7: P3-GATE-07 sensor check ---"
CC_LIST=$(kubectl exec -n ${NS} peer0-i3tech -- \
  peer chaincode list --instantiated -C ford-channel 2>/dev/null || echo "")

if echo "${CC_LIST}" | grep -q "membership-registry"; then
  echo "P3-GATE-07: PASS — membership-registry instantiated on ford-channel"
else
  echo "P3-GATE-07: FAIL — membership-registry not found in instantiated list"
  echo "Chaincode list output: ${CC_LIST}"
  exit 1
fi

echo ""
echo "=== P3-GATE-06 + P3-GATE-07 bootstrap complete ==="
echo "    Next: test fabric_tx_id in FORD /register response:"
echo "    curl -s -X POST https://api.i3technologies.co.ke/ford/api/v1/members/register \\"
echo "      -H 'Authorization: Bearer \$TOKEN' \\"
echo "      -d '{\"national_id\":\"12345678\",\"phone\":\"+254700000001\",\"ward_code\":\"001\",\"constituency\":\"test\",\"county\":\"Machakos\",\"agent_id\":\"AGENT-00000001\",\"consent\":true}'"
echo "    Expected: 201 with fabric_tx_id field present"
