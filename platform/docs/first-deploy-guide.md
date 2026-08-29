# i3 Unified Platform — First Deploy Guide
# From Zero to Cluster Live

> **Total estimated time:** ~90 minutes (ROKS provisioning ~70 min, operator/app deploy ~20 min)  
> **Prerequisites:** IBM Cloud API key in `.env`, IBM Cloud CLI + plugins installed, Terraform ≥ 1.7, `oc` CLI

---

## Phase 0 — Local Setup (5 min)

```powershell
# 1. Load environment variables (reads .env, sets TF_VAR_* in current session)
. .\platform\scripts\load-env.ps1

# Expected output:
#   Loaded N environment variables.
#   Key values set:
#     IBMCLOUD_API_KEY      : Hz4n9...[redacted]
#     TF_VAR_region         : eu-de
#     TF_VAR_resource_group : i3-production

# 2. Verify IBM Cloud CLI is logged in and pointing at the right target
.\platform\scripts\validate-step3.ps1

# All 9 checks should pass. If "Not logged in":
ibmcloud login --apikey $env:IBMCLOUD_API_KEY -r eu-de -g i3-production
```

---

## Phase 1 — Terraform: VPC + COS + IAM + ROKS (~70 min)

```powershell
# 3. Import any orphaned IAM resources (safe to run even if state is clean)
.\platform\scripts\terraform-import-iam.ps1

# 4. Plan infrastructure (review before applying)
cd platform\terraform
terraform plan -var="ibmcloud_api_key=$env:IBMCLOUD_API_KEY" -out=tfplan.out
cd ..\..

# Review: Terraform will create/update:
#   + module.vpc.*         (VPC, 3 subnets, security groups)
#   + module.cos.*         (4 COS buckets if not already present)
#   + module.iam.*         (service IDs, policies, trusted profile)
#   + module.roks.*        (ROKS 4.15 cluster, worker pool: 2×bx2.4x16, GPU pool: 0)

# 5. Apply (this takes ~70 minutes — ROKS cluster provisioning)
cd platform\terraform
terraform apply tfplan.out
cd ..\..

# Monitor worker nodes in a separate terminal:
make watch-workers
```

**After apply completes:**
```powershell
# 6. Fetch kubeconfig
ibmcloud ks cluster config --cluster i3-platform
oc cluster-info
```

---

## Phase 2 — Namespace & NetworkPolicy Layer (2 min)

```powershell
# 7. Create all 11 managed namespaces with ResourceQuotas and NetworkPolicies
make deploy-namespaces

# Verify
make verify-namespaces
```

---

## Phase 3 — Operators (5 min apply, ~10 min for pods to become Ready)

```powershell
# 8. Subscribe to OLM operators (Crunchy, Strimzi, RHSSO)
oc apply -f platform/operators/subscriptions/operator-subscriptions.yaml

# Wait for operator pods
oc rollout status deployment -n openshift-operators --timeout=5m

# 9. Deploy all operators
make deploy-operators

# Monitor:
oc get pods -n i3-data -w          # PostgreSQL HA (3 pods)
oc get pods -n i3-messaging -w     # Kafka KRaft (3 pods)
oc get pods -n i3-security -w      # OpenBao (3 pods)
oc get pods -n i3-auth -w          # Keycloak (2 pods)
```

---

## Phase 4 — OpenBao Bootstrap (Manual Gate — ~10 min)

> ⚠ **CRITICAL** — This section must be done manually. Do not skip.

```bash
# 10. Initialize OpenBao (generates Shamir keys)
oc exec -n i3-security openbao-0 -- bao operator init \
  -key-shares=5 -key-threshold=3 \
  -format=json > /tmp/openbao-init.json

# ⚠ IMMEDIATELY save /tmp/openbao-init.json to your offline HSM/paper vault
# NEVER commit this file. The .gitignore excludes it.

# 11. Unseal all 3 pods with 3-of-5 keys
```

```powershell
# On Windows — add unseal keys to .env and run the PowerShell unsealer:
# Edit .env:
#   OPENBAO_UNSEAL_KEY_1=<key1-from-openbao-init.json>
#   OPENBAO_UNSEAL_KEY_2=<key2-from-openbao-init.json>
#   OPENBAO_UNSEAL_KEY_3=<key3-from-openbao-init.json>

. .\platform\scripts\load-env.ps1
.\platform\scripts\unseal-openbao.ps1
```

```bash
# 12. Apply the bootstrap Job (configures KV v2, K8s auth, namespace policies)
oc apply -f platform/operators/openbao/openbao-bootstrap-scripts.yaml

# 13. Create root-token secret so the Job can authenticate
ROOT_TOKEN=$(cat /tmp/openbao-init.json | jq -r '.root_token')
oc create secret generic openbao-root-token \
  -n i3-security --from-literal=token=$ROOT_TOKEN

oc wait --for=condition=complete job/openbao-bootstrap -n i3-security --timeout=5m

# 14. Revoke root token (SECURITY HARDENING — must do this!)
oc exec -n i3-security openbao-0 -- bao token revoke $ROOT_TOKEN
oc delete secret openbao-root-token -n i3-security
```

---

## Phase 5 — Populate Application Secrets (5 min)

```powershell
# 15. Write all application secrets into OpenBao KV v2
#     (generates random keys for LiteLLM, Langfuse, Directus, n8n, Grafana, etc.)
$env:OPENBAO_ROOT_TOKEN = "<root-token-from-step-13>"
.\platform\scripts\populate-vault.ps1

# Note: The root token is revoked AFTER this step. Run populate-vault.ps1
# BEFORE step 14 (revoke), or create a temporary admin token:
#   oc exec -n i3-security openbao-0 -- bao token create -policy=root -ttl=30m
```

---

## Phase 6 — Application Workstreams (5 min apply)

```powershell
# 16. Deploy all application stacks in the correct order
make deploy-gateway       # LiteLLM, Ollama, Langfuse
make deploy-keda          # KEDA autoscaler + ScaledObjects
make deploy-evalos        # EvalOS sandbox + exam engine
make deploy-ott           # OvenMediaEngine, Nginx, SeaweedFS, Directus, n8n
make deploy-admissions    # ChromaDB, Admissions agent, MCP connectors
make deploy-monitoring    # Prometheus + Grafana

# Monitor all namespaces at once:
oc get pods -A -w | grep -E "i3-(model-gateway|evalos|ott|admissions|monitoring)"
```

---

## Phase 7 — Post-Deploy Configuration (15 min)

```powershell
# 17. Keycloak: regenerate client secrets and write to OpenBao
$env:KEYCLOAK_ADMIN_PASSWORD = "admin"   # default — change immediately after
.\platform\scripts\keycloak-post-deploy.ps1

# 18. SeaweedFS DR: create the rclone-secrets Kubernetes Secret
.\platform\scripts\rclone-secret.ps1

# 19. DNS: get the OpenShift Ingress hostname and add CNAME records
oc get ingresscontroller default -n openshift-ingress-operator -o jsonpath='{.status.domain}'
# Output example: i3-platform-XXXXXXXX-0000.eu-de.containers.appdomain.cloud
# See: platform/docs/dns-setup.md for the full CNAME list
```

---

## Phase 8 — Validation

```powershell
# 20. Run the full post-deploy health check
.\platform\scripts\post-deploy-checklist.ps1

# 21. Run Argo CD verification
make verify-argo

# 22. Full cluster verification
make verify-cluster
```

---

## Phase 9 — Build & Push Custom Images (5 min)

```bash
# 23. Log in to IBM Container Registry
ibmcloud cr login --client buildah

# 24. Build and push all 3 custom images
make build-images

# Images pushed to:
#   de.icr.io/i3-platform/evalos-sandbox:latest
#   de.icr.io/i3-platform/admissions-agent:latest
#   de.icr.io/i3-platform/mcp-connectors:latest
```

---

## Phase 10 — EvalOS Database Migration

```bash
# 25. Run the EvalOS schema migration
oc exec -n i3-data \
  $(oc get pods -n i3-data -l postgres-operator.crunchydata.com/role=master \
    -o jsonpath='{.items[0].metadata.name}') \
  -- psql -U postgres -d evalos_db \
  -f /dev/stdin < platform/evalos/schema.sql
```

---

## Deploy Complete ✓

**Estimated total time:** ~90–100 minutes

| Milestone | Status |
|---|---|
| ROKS cluster provisioned | ✓ |
| 11 managed namespaces live | ✓ |
| PostgreSQL HA + Kafka KRaft | ✓ |
| OpenBao unsealed & bootstrapped | ✓ |
| All secrets populated | ✓ |
| All applications deployed | ✓ |
| Keycloak clients configured | ✓ |
| SeaweedFS DR sync configured | ✓ |
| DNS CNAMEs pointing to cluster | See dns-setup.md |
| Health check passing | ✓ |

---

## Month 3 Milestone: RHOAI Operator

After the initial platform is stable, install Red Hat OpenShift AI for the AI Lab:

```bash
# Create RHOAI subscription
cat <<EOF | oc apply -f -
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: rhods-operator
  namespace: redhat-ods-operator
spec:
  channel: stable
  name: rhods-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF

# Provision AI Lab cohort namespaces
make provision-cohort COHORT=1 STUDENTS="alice,bob,carol"
```

---

*See also:*  
- [`platform/RUNBOOK.md`](../RUNBOOK.md) — Day-2 operations  
- [`platform/docs/dns-setup.md`](dns-setup.md) — DNS CNAME configuration  
- [`platform/docs/cos-recovery-runbook.md`](cos-recovery-runbook.md) — COS incident recovery
