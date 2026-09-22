# Fabric Orderer MSP Bootstrap — Deferred to Phase 3

## Status
`i3-ford/orderer-0` is in CrashLoopBackOff. Root cause: MSP crypto material
(signcerts, keystore, cacerts) was never generated via `fabric-ca-client enroll`.

## Root Cause Chain
1. `permission denied: mkdir /var/hyperledger/production/msp` — fixed via fsGroup+chown init container ✅
2. `no such file or directory: /var/hyperledger/production/msp/signcerts` — MSP material missing ⬜

## What Is Missing
The orderer needs enrollment against `ford-ca` to generate:
- `/var/hyperledger/production/msp/signcerts/cert.pem`
- `/var/hyperledger/production/msp/keystore/<key>.pem`
- `/var/hyperledger/production/msp/cacerts/ca.pem`
- `/var/hyperledger/production/msp/admincerts/`

## Fix (Phase 3 — HC-2 deadline: November 2026)
```bash
# 1. Enroll orderer identity against ford-ca
export FABRIC_CA_CLIENT_HOME=/tmp/orderer-msp
fabric-ca-client enroll \
  -u https://orderer:ordererpasswd@ford-ca.i3-ford.svc.cluster.local:7054 \
  --caname ford-ca \
  --tls.certfiles /etc/hyperledger/fabric/tls/ca.crt

# 2. Package MSP material as a Kubernetes secret
kubectl create secret generic orderer-msp -n i3-ford \
  --from-file=signcerts=$FABRIC_CA_CLIENT_HOME/msp/signcerts/cert.pem \
  --from-file=keystore=$FABRIC_CA_CLIENT_HOME/msp/keystore/ \
  --from-file=cacerts=$FABRIC_CA_CLIENT_HOME/msp/cacerts/

# 3. Mount secret into orderer StatefulSet at /var/hyperledger/production/msp
```

## Gate Impact
- P1: Not a gate requirement — orderer first required at P3-GATE-05
- P3-GATE-05: `kubectl get pod -n i3-ford -l app=hlf-peer` → 3 Running
- P3-GATE-06: `peer chaincode list --instantiated -C ford-channel`
- HC-2: Chaincode staged by November 2026 for 16 March 2027 IEBC deadline

## SCC Fix Applied (permanent)
```bash
oc adm policy add-scc-to-user anyuid -z ford-sa -n i3-ford
```
Init container `fix-permissions` (busybox:1.35) added to StatefulSet to chown
`/var/hyperledger/production/orderer` on each pod start.
