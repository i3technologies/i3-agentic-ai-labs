# i3 Unified Platform — Day-2 Operations Runbook
# Disaster Recovery, Incident Response, and Operational Procedures

---

## 1. CLUSTER ORIENTATION

```bash
# Log in to IBM Cloud + ROKS
ibmcloud login --apikey $IBMCLOUD_API_KEY -r eu-de -g i3-production
ibmcloud ks cluster config --cluster i3-platform
oc cluster-info

# Verify 17-namespace topology (solutions 01-08 must be UNTOUCHED)
make verify-cluster
```

**Namespace Topology:**

| Namespace | Purpose | Touch? |
|---|---|---|
| `i3-data` | Crunchy PostgreSQL HA | Managed |
| `i3-messaging` | Strimzi Kafka KRaft | Managed |
| `i3-security` | OpenBao Vault | Managed |
| `i3-auth` | Keycloak SSO | Managed |
| `i3-gitops` | Argo CD + Tekton | Managed |
| `i3-model-gateway` | LiteLLM + vLLM + Langfuse | Managed |
| `i3-ai-lab` | RHOAI + cohort namespaces | Managed |
| `i3-evalos` | EvalOS + Firecracker sandbox | Managed |
| `i3-ott` | OME + Nginx + SeaweedFS | Managed |
| `i3-admissions` | FastAPI + ChromaDB + MCP | Managed |
| `i3-monitoring` | Prometheus + Grafana + OTel | Managed |
| `solution-01` … `solution-08` | Industry AI Solutions | **DO NOT TOUCH** |

---

## 2. OPENBAO BOOTSTRAP (Manual Gate — One-Time Procedure)

```bash
# Step 1: Deploy OpenBao StatefulSet (do NOT apply bootstrap Job yet)
oc apply -f platform/operators/openbao/openbao-deploy.yaml

# Step 2: Wait for pods
oc rollout status statefulset/openbao -n i3-security

# Step 3: Initialize (3-of-5 Shamir threshold)
oc exec -n i3-security openbao-0 -- bao operator init \
  -key-shares=5 -key-threshold=3 \
  -format=json > /tmp/openbao-init.json
# ⚠ Store /tmp/openbao-init.json in your offline HSM/paper vault immediately
# ⚠ NEVER commit this file to git

# Step 4: Unseal all 3 nodes (repeat 3 times with different keys)
for pod in openbao-0 openbao-1 openbao-2; do
  for key in $(cat /tmp/openbao-init.json | jq -r '.unseal_keys_b64[:3][]'); do
    oc exec -n i3-security $pod -- bao operator unseal $key
  done
done

# Step 5: Create root-token secret for bootstrap Job
ROOT_TOKEN=$(cat /tmp/openbao-init.json | jq -r '.root_token')
oc create secret generic openbao-root-token \
  -n i3-security \
  --from-literal=token=$ROOT_TOKEN

# Step 6: Apply Ansible bootstrap Job (configures KV, K8s auth, policies)
oc apply -f platform/operators/openbao/openbao-bootstrap-job.yaml
oc wait --for=condition=complete job/openbao-bootstrap -n i3-security --timeout=5m

# Step 7: Revoke root token (security hardening)
oc exec -n i3-security openbao-0 -- bao token revoke $ROOT_TOKEN
oc delete secret openbao-root-token -n i3-security
```

---

## 3. POSTGRESQL BACKUP & RESTORE

### 3.1 Verify Backup Health
```bash
# Check pgBackRest stanza status
oc exec -n i3-data \
  $(oc get pods -n i3-data -l postgres-operator.crunchydata.com/role=pgbackrest \
    -o jsonpath='{.items[0].metadata.name}') \
  -- pgbackrest --stanza=db info

# Trigger manual full backup
make dr-backup
```

### 3.2 Point-in-Time Recovery (PITR)
```bash
# Scale down all applications that write to Postgres FIRST
oc scale deployment -n i3-model-gateway --all --replicas=0
oc scale deployment -n i3-admissions --all --replicas=0
oc scale deployment -n i3-evalos --all --replicas=0

# Restore to specific timestamp
make dr-restore RESTORE_TARGET="2025-09-01 03:00:00"

# Monitor restore progress
oc logs -n i3-data -l postgres-operator.crunchydata.com/role=pgbackrest -f

# Once primary is healthy, restore Patroni leadership and scale apps back
oc scale deployment -n i3-model-gateway --all --replicas=2
oc scale deployment -n i3-admissions --all --replicas=2
oc scale deployment -n i3-evalos --all --replicas=2
```

### 3.3 Emergency PostgreSQL Failover
```bash
# Check cluster topology
oc exec -n i3-data \
  $(oc get pods -n i3-data -l postgres-operator.crunchydata.com/role=master \
    -o jsonpath='{.items[0].metadata.name}') \
  -- patronictl -c /etc/patroni topology

# Manually trigger failover if primary is unresponsive
oc exec -n i3-data \
  $(oc get pods -n i3-data -l postgres-operator.crunchydata.com/role=replica \
    -o jsonpath='{.items[0].metadata.name}') \
  -- patronictl -c /etc/patroni failover i3-postgres --master <old-primary-pod>
```

---

## 4. SEAWEEDFS → IBM COS DISASTER RECOVERY

### 4.1 Verify Replication Lag
```bash
# Check last successful rclone sync job
oc get jobs -n i3-ott -l job-name=seaweedfs-cos-dr-sync --sort-by=.metadata.creationTimestamp

# Manual sync (immediate DR protection)
make dr-backup

# Verify object counts match
oc run rclone-check --rm -i --restart=Never --image=rclone/rclone:1.67 \
  -n i3-ott --env-from=secret/rclone-secrets \
  -- rclone check seaweedfs:i3-vod cos:i3-seaweedfs-dr-eu-de/vod
```

### 4.2 Restore SeaweedFS from IBM COS
```bash
# If SeaweedFS is total loss — restore from COS to new SeaweedFS cluster
# 1. Deploy fresh SeaweedFS
oc apply -f platform/ott/seaweedfs/seaweedfs-deploy.yaml
oc rollout status statefulset/seaweedfs-master -n i3-ott

# 2. Restore via rclone
oc run rclone-restore --rm -i --restart=Never --image=rclone/rclone:1.67 \
  -n i3-ott --env-from=secret/rclone-secrets \
  -- rclone sync cos:i3-seaweedfs-dr-eu-de/vod seaweedfs:i3-vod \
     --transfers=32 --progress
```

---

## 5. GPU BURST POOL MANAGEMENT

```bash
# Activate GPU pool before training / heavy inference
make gpu-up

# Monitor GPU utilization
oc exec -n i3-model-gateway \
  $(oc get pods -n i3-model-gateway -l app=vllm-gpu -o jsonpath='{.items[0].metadata.name}') \
  -- nvidia-smi

# KEDA will auto-scale down after cooldownPeriod=300s of low queue depth
# Force immediate scale-down (cost-saving)
make gpu-down
```

---

## 6. KAFKA KRAFT OPERATIONS

```bash
# Check broker health
oc exec -n i3-messaging \
  $(oc get pods -n i3-messaging -l strimzi.io/component-type=kafka -o jsonpath='{.items[0].metadata.name}') \
  -- bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092

# List consumer group lag
oc exec -n i3-messaging \
  $(oc get pods -n i3-messaging -l strimzi.io/component-type=kafka -o jsonpath='{.items[0].metadata.name}') \
  -- bin/kafka-consumer-groups.sh \
     --bootstrap-server localhost:9092 --describe --all-groups

# Reassign partitions after node failure
oc exec -n i3-messaging \
  $(oc get pods -n i3-messaging -l strimzi.io/component-type=kafka -o jsonpath='{.items[0].metadata.name}') \
  -- bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 \
     --reassignment-json-file /tmp/reassignment.json --execute
```

---

## 7. KEYCLOAK SESSION MANAGEMENT

```bash
# List active Keycloak sessions for i3 realm
oc exec -n i3-auth \
  $(oc get pods -n i3-auth -l app=keycloak -o jsonpath='{.items[0].metadata.name}') \
  -- /opt/keycloak/bin/kcadm.sh get sessions/realm \
     --server https://localhost:8443 \
     --realm master \
     --user admin

# Force refresh JWKS cache (after key rotation)
curl -sk https://sso.i3technologies.co.ke/realms/i3/protocol/openid-connect/certs | jq .
```

---

## 8. ARGO CD SYNC RUNBOOK

```bash
# Check sync status
oc get applications -n i3-gitops

# Force sync a specific workstream
oc patch application i3-model-gateway -n i3-gitops \
  --type=merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'

# Rollback to previous revision
oc exec -n i3-gitops \
  $(oc get pods -n i3-gitops -l app.kubernetes.io/name=argocd-server -o jsonpath='{.items[0].metadata.name}') \
  -- argocd app rollback i3-model-gateway --revision <commit-sha>
```

---

## 9. 6-MONTH ROLLOUT MILESTONES

| Month | Milestone | Namespaces Active |
|---|---|---|
| M1 | Infrastructure + GitOps baseline | `i3-data`, `i3-messaging`, `i3-security`, `i3-auth`, `i3-gitops` |
| M2 | Model Gateway + Langfuse | + `i3-model-gateway` |
| M3 | EvalOS sandbox (Profiles A+B) | + `i3-evalos` |
| M4 | OTT streaming + media pipeline | + `i3-ott` |
| M5 | Admissions Agent + MCP connectors | + `i3-admissions` |
| M6 | AI Lab cohorts + full test suite | + per-cohort namespaces |

---

## 10. BUDGET GUARDRAILS (≤$1,500/mo)

| Resource | State | Est. Cost |
|---|---|---|
| 3× bx2.4x16 CPU workers | Always on | ~$420/mo |
| GPU burst gx2.8x64 pool | Scale-to-zero | ~$0–$280/mo (on-demand) |
| IBM COS storage | ~2 TB | ~$45/mo |
| ROKS control plane | Included in entitlement | $0 |
| OCP worker licensing | `entitlement=cloud_pak` (MW02049) | $0 |
| SeaweedFS PVCs (500Gi×3) | Retain | ~$300/mo |
| **Total (GPU off)** | | **~$765/mo** |
| **Total (GPU burst 50% time)** | | **~$905/mo** |

Run `make gpu-down` whenever GPU workloads are idle to stay within budget.
