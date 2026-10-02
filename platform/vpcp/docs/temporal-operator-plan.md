# Temporal Workflow Engine — Operator Evaluation & Resource Plan
# File: platform/vpcp/docs/temporal-operator-plan.md
# Context: i3 AI Platform — Pre-Plan Phase Gate for Application 2 (VPCP)

## 1. Compatibility Check

| Requirement | i3 Platform Status | Result |
|---|---|---|
| PostgreSQL 12+ (Temporal persistence backend) | Crunchy PostgreSQL 16 ✅ | COMPATIBLE |
| Kubernetes 1.25+ | ROKS 4.16 (K8s 1.29) ✅ | COMPATIBLE |
| Namespace isolation | Temporal deployed in i3-vpcp-core ✅ | COMPATIBLE |
| Redis (Temporal visibility — optional) | Redis cluster available ✅ | COMPATIBLE |
| OpenShift SCCs | Temporal pods run as non-root — needs restricted-v2 SCC | CONFIRMED SAFE |

**Compatibility verdict: APPROVED for installation on existing ROKS cluster.**

---

## 2. Temporal Architecture on i3 Platform

```
i3-vpcp-core namespace:
  temporal-server      (1 replica — can scale to 3 for HA)
  temporal-ui          (1 replica — internal dashboard only)
  vpcp-temporal-worker (2 replicas — deal_registration workflow workers)

Shared infrastructure (no new installs):
  Crunchy PostgreSQL 16   → temporal_db (new database on existing cluster)
  Redis cluster           → Temporal visibility store (optional — use DB if skipped)
  OpenBao KV v2           → i3/vpcp/temporal-db-url  (injected via ExternalSecrets)
```

---

## 3. Resource Requirements

| Component | Replicas | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---|---|---|---|---|---|
| temporal-server | 1 (Phase 1); 3 (HA) | 500m | 2000m | 512 Mi | 2 Gi |
| temporal-ui | 1 | 100m | 500m | 128 Mi | 512 Mi |
| vpcp-temporal-worker | 2 | 250m | 1000m | 256 Mi | 1 Gi |
| **Total** | **4** | **1.1 CPU** | **5 CPU** | **1.15 Gi** | **5.5 Gi** |

**Fits within i3-vpcp-core namespace quota: 4 CPU / 8 Gi (as defined in Namespace Plan).**

---

## 4. Database: temporal_db

Create on existing Crunchy PostgreSQL cluster:

```sql
-- Run as PostgreSQL superuser on the Crunchy cluster
CREATE DATABASE temporal_db;
CREATE USER temporal_user WITH PASSWORD '<from-OpenBao-i3/vpcp/temporal-db-url>';
GRANT ALL PRIVILEGES ON DATABASE temporal_db TO temporal_user;

-- HC-4 note: Temporal manages its own schema internally.
-- The temporal_db is NOT shared with vpcp_db.
-- No tenant_id RLS needed on Temporal's internal tables —
-- Temporal's workflow namespace isolation provides the equivalent boundary.
```

OpenBao secret path: `i3/vpcp/temporal-db-url`
Value: `postgresql://temporal_user:<password>@crunchy-pgbouncer.i3-data.svc:5432/temporal_db`

---

## 5. Installation Steps (Helm — to be executed in Implement Phase)

```bash
# Step 1: Add Temporal Helm repo
helm repo add temporal https://go.temporal.io/server/releases/helm-chart
helm repo update

# Step 2: Create namespace and RBAC
oc new-project i3-vpcp-core
oc create sa temporal-sa -n i3-vpcp-core
oc adm policy add-scc-to-user restricted-v2 -z temporal-sa -n i3-vpcp-core

# Step 3: Create ExternalSecret for temporal-db-url
# (ExternalSecret CR references OpenBao i3/vpcp/temporal-db-url)

# Step 4: Install Temporal with PostgreSQL backend
helm install temporal temporal/temporal \
  --namespace i3-vpcp-core \
  --set server.replicaCount=1 \
  --set server.config.persistence.default.driver=sql \
  --set server.config.persistence.default.sql.driver=postgres12 \
  --set server.config.persistence.default.sql.host=crunchy-pgbouncer.i3-data.svc \
  --set server.config.persistence.default.sql.port=5432 \
  --set server.config.persistence.default.sql.database=temporal_db \
  --set server.config.persistence.default.sql.user=temporal_user \
  --set server.config.persistence.default.sql.existingSecret=temporal-db-secret \
  --set web.enabled=true \
  --set web.service.type=ClusterIP \
  --set admintools.enabled=true \
  --set grafana.enabled=false \
  --set prometheus.enabled=false \
  --set elasticsearch.enabled=false

# Step 5: Create VPCP temporal namespace
kubectl exec -it deploy/temporal-admintools -n i3-vpcp-core -- \
  tctl --namespace vpcp-deals namespace register \
  --retention 7 \
  --description "VPCP deal registration workflows"

# Step 6: Verify
kubectl get pods -n i3-vpcp-core -l app.kubernetes.io/name=temporal
```

---

## 6. Security Hardening

- Temporal Web UI accessible only within cluster (ClusterIP, no OpenShift Route)
- Temporal gRPC service (port 7233) accessible only from i3-vpcp-core namespace
- NetworkPolicy: allow egress from vpcp-temporal-worker only to temporal-server:7233 and
  crunchy-pgbouncer.i3-data:5432 and mcp-gateway.i3-agent-mesh:8000
- Temporal mTLS: enable in Phase 2 using cluster-internal cert-manager certificates
- No direct database access from worker pods — workers only talk to Temporal server

---

## 7. HC Compliance in Temporal Workflows

- **HC-4:** DealRequest.tenant_id is MANDATORY (enforced in DealRequest.__post_init__).
  Temporal workflow namespaces provide an additional isolation boundary.
- **HC-5:** syncToIbmSalesCloud routes through MCP Gateway Tier 3 gate
  (vpcp.ibm_sales_cloud.sync tool). Fixed in platform/vpcp/workflows/deal_registration.py.
- **HC-7:** No DEV_BYPASS_AUTH in any Temporal configuration files.

---

## 8. Rollback Plan

If Temporal install fails or causes cluster instability:

```bash
# Remove Temporal (does not affect vpcp_db or Crunchy cluster)
helm uninstall temporal -n i3-vpcp-core

# temporal_db can be retained for audit trail or dropped:
# DROP DATABASE temporal_db;  -- only if confirmed clean
```

VPCP Core API falls back to direct async DB saga pattern (without Temporal durability)
until Temporal is re-installed. Deal registration continues; durability guarantees are
reduced to standard asyncpg transaction semantics.
