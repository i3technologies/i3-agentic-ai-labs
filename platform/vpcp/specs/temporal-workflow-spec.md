# VPCP — Temporal Workflow Specification
# File: platform/vpcp/specs/temporal-workflow-spec.md
# Namespace: vpcp-deals  (Temporal namespace, not OpenShift)
# Service: i3-vpcp-core (OpenShift namespace)
#
# HC-4: tenant_id MANDATORY on every DealRequest, activity, and CloudEvent.
# HC-5: IBM Sales Cloud sync routes ONLY through MCP Gateway Tier 3 gate.
# HC-3: Agents propose — commercial desk disposes.  No L2/L3 auto-approval.

---

## 1. Workflow Overview

```
DealRegistrationWorkflow (Temporal)
══════════════════════════════════════════════════════════════════════════

  INPUT: DealRequest {
    deal_id, tenant_id*, customer_account, product_family,
    estimated_arr_usd, partner_id, expected_close_date
  }

  Step 1 ─ checkDealConflict()
    │  Query vpcp_db.deals WHERE tenant_id=$1
    │       AND customer_account=$2 AND product_family=$3
    │       AND created_at > now()-90d AND status NOT IN ('REJECTED','EXPIRED')
    ├─ conflict? ──YES──→ notifyCommercialDesk()
    │                        └─ emit CloudEvent: i3.vpcp.deal.conflict_flagged
    │                        └─ return CONFLICT_FLAGGED_FOR_ARBITRATION
    └─ no conflict ─────→ Step 2

  Step 2 ─ await commercial_desk_approved signal (timeout: 48 h)
    │  (Signal source: POST /v1/deals/{dealId}/approve — HC-3 human gate)
    ├─ timeout / rejected ──→ return DEAL_REJECTED
    └─ approved ─────────→ Step 3

  Step 3 ─ mcp_sync_to_ibm_sales_cloud()
    │  HC-5: POST /tools/vpcp.ibm_sales_cloud.sync/invoke  [MCP Gateway]
    ├─ HTTP 202 (PENDING) ──→ set _approval_id via set_mcp_approval_id signal
    │                          await set_mcp_approval_id signal (timeout: 48 h)
    │                          ├─ timeout ──→ return DEAL_REJECTED
    │                          └─ approved → re-invoke mcp_sync (with approval_id)
    ├─ HTTP 200 (APPROVED) ──→ emit CloudEvent: i3.vpcp.deal.registered
    │                          return DEAL_REGISTERED_AND_SYNCED_IBM
    └─ error ────────────→ RetryPolicy(max=3) → DEAL_REJECTED

  OUTPUT: one of
    "DEAL_REGISTERED_AND_SYNCED_IBM"
    "CONFLICT_FLAGGED_FOR_ARBITRATION"
    "DEAL_REJECTED"
```

---

## 2. Temporal Configuration

### 2.1 Namespace

```yaml
namespace: vpcp-deals
retention_days: 7          # workflow history retained 7 days
description: "VPCP deal registration and IBM Sales Cloud sync workflows"
```

### 2.2 Task Queue

```python
TASK_QUEUE = "vpcp-deal-registration"
```

### 2.3 Retry Policies

```python
# Activities: 3 attempts, exponential back-off (2×)
ACTIVITY_RETRY = RetryPolicy(
    maximum_attempts=3,
    backoff_coefficient=2.0,
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=5),
    non_retryable_error_types=["HC4ViolationError", "HC5ViolationError"],
)

# Activities timeout
ACTIVITY_OPTIONS = {
    "start_to_close_timeout": timedelta(minutes=5),
    "retry_policy": ACTIVITY_RETRY,
}

# Approval wait windows
COMMERCIAL_APPROVAL_TIMEOUT = timedelta(hours=48)
MCP_APPROVAL_TIMEOUT        = timedelta(hours=48)
```

---

## 3. Workflow Definition (Python / Temporal SDK)

> Full implementation at [`deal_registration.py`](../workflows/deal_registration.py).
> This section specifies the canonical state machine and signal/query contracts.

### 3.1 Workflow Class

```python
@workflow.defn
class DealRegistrationWorkflow:
    """
    Saga for VPCP deal registration with durable Temporal state.

    Signals (external → workflow):
      commercial_desk_approved()         — HC-3: human commercial desk gate
      set_mcp_approval_id(approval_id)   — HC-5: MCP Gateway Tier 3 approved

    Queries (external → read workflow state):
      get_status()  → DealStatus enum

    HC-4: tenant_id in DealRequest.__post_init__ guard (fails fast if missing).
    HC-5: all IBM Sales Cloud calls route via mcp_sync_to_ibm_sales_cloud().
    HC-3: no auto-approval — signals come from authenticated human approvers.
    """
```

### 3.2 Signals

| Signal                      | Sender                     | Purpose                                |
|-----------------------------|----------------------------|----------------------------------------|
| `commercial_desk_approved`  | VPCP Core API (`/approve`) | Advances workflow past 48 h human gate |
| `set_mcp_approval_id`       | MCP Gateway polling worker | Passes Tier 3 approval ID to workflow  |

### 3.3 Queries

| Query        | Returns       | Notes                                              |
|--------------|---------------|----------------------------------------------------|
| `get_status` | `DealStatus`  | Safe read of current workflow state (no mutation)  |

---

## 4. Activities

### 4.1 `check_deal_conflict`

```python
@activity.defn
async def check_deal_conflict(request: DealRequest) -> ConflictCheckResult:
    """
    HC-4: query scoped by tenant_id using asyncpg pool.
    SQL pattern:
      SELECT id FROM vpcp_db.deals
       WHERE tenant_id = $1
         AND customer_account = $2
         AND product_family = $3
         AND created_at > now() - INTERVAL '90 days'
         AND status NOT IN ('REJECTED', 'EXPIRED')
      LIMIT 1;
    """
```

**Input:** `DealRequest`  
**Output:** `ConflictCheckResult { has_conflict: bool, conflicting_deal_id: str|None, tenant_id: str }`

### 4.2 `notify_commercial_desk`

```python
@activity.defn
async def notify_commercial_desk(request: DealRequest, conflicting_deal_id: str) -> None:
    """
    Emits i3.vpcp.deal.conflict_flagged CloudEvent to Kafka topic
    'i3.vpcp.deal.events' and sends notification email.

    CloudEvent envelope (HC-4: tenantid required):
      specversion: "1.0"
      type:        "i3.vpcp.deal.conflict_flagged"
      source:      "vpcp-core-api"
      tenantid:    <request.tenant_id>      ← HC-4
      data:
        deal_id:              <uuid>
        conflicting_deal_id:  <uuid>
        customer_account:     <str>
        product_family:       <str>
    """
```

### 4.3 `mcp_sync_to_ibm_sales_cloud`

```python
@activity.defn
async def mcp_sync_to_ibm_sales_cloud(request: DealRequest) -> McpSyncResult:
    """
    HC-5: ONLY code path that touches IBM Sales Cloud — routes via MCP Gateway.

    Phase 1 call (no approval_id):
      POST {MCP_GATEWAY_URL}/tools/vpcp.ibm_sales_cloud.sync/invoke
      Headers:
        Authorization:  Bearer {VPCP_AGENT_JWT}   ← from OpenBao i3/vpcp/agent-jwt
        X-Agent-Id:     vpcp-deal-agent
        X-Tenant-Id:    {request.tenant_id}        ← HC-4
      Body:
        { "input": { deal_id, customer_account, product_family,
                     estimated_arr_usd, partner_id, tenant_id } }
      Response 202 → return McpSyncResult(approval_status="pending", approval_id=...)

    Phase 2 call (after set_mcp_approval_id signal):
      POST {MCP_GATEWAY_URL}/tools/vpcp.ibm_sales_cloud.sync/invoke
      Body includes: { "approval_id": <uuid> }
      Response 200 → return McpSyncResult(success=True, ibm_sales_cloud_ref=...)
    """
```

**Output:** `McpSyncResult { success: bool, ibm_sales_cloud_ref: str|None, approval_id: str|None, approval_status: str, tenant_id: str }`

---

## 5. CloudEvents Topology (Strimzi Kafka)

### 5.1 Topic Configuration

```yaml
# Strimzi KafkaTopic CRs — deploy to i3-kafka namespace
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: i3.vpcp.deal.events
  namespace: i3-kafka
  labels:
    strimzi.io/cluster: i3-kafka
spec:
  partitions: 6          # 6 partitions → parallelism for 6 product families
  replicas: 3            # RF=3 for durability on 3-broker Strimzi cluster
  config:
    retention.ms: "604800000"    # 7 days
    cleanup.policy: delete
    min.insync.replicas: "2"
    compression.type: snappy
---
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: i3.vpcp.partner.events
  namespace: i3-kafka
  labels:
    strimzi.io/cluster: i3-kafka
spec:
  partitions: 3
  replicas: 3
  config:
    retention.ms: "604800000"
    cleanup.policy: delete
    min.insync.replicas: "2"
    compression.type: snappy
```

### 5.2 CloudEvent Envelope (all events)

All VPCP CloudEvents MUST include the following 9-field envelope:

```json
{
  "specversion": "1.0",
  "id":          "<uuid-v4>",
  "source":      "vpcp-core-api",
  "type":        "i3.vpcp.deal.<event_name>",
  "time":        "<ISO-8601>",
  "tenantid":    "<tenant_id-uuid>",
  "datacontenttype": "application/json",
  "partitionkey": "<deal_id>",
  "data": { ... }
}
```

**HC-4**: `tenantid` is a MANDATORY envelope field on every CloudEvent.

### 5.3 Event Catalogue

#### `i3.vpcp.deal.registered`

Emitted when `DealRegistrationWorkflow` returns `DEAL_REGISTERED_AND_SYNCED_IBM`.

```json
{
  "specversion": "1.0",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "vpcp-core-api",
  "type": "i3.vpcp.deal.registered",
  "time": "2025-07-21T10:00:00Z",
  "tenantid": "a1b2c3d4-0000-0000-0000-000000000001",
  "datacontenttype": "application/json",
  "partitionkey": "d1b2c3d4-0000-0000-0000-000000000003",
  "data": {
    "deal_id":             "d1b2c3d4-0000-0000-0000-000000000003",
    "tenant_id":           "a1b2c3d4-0000-0000-0000-000000000001",
    "customer_account":    "Acme Corporation Kenya",
    "product_family":      "watsonx",
    "estimated_arr_usd":   125000.00,
    "partner_id":          "b1b2c3d4-0000-0000-0000-000000000002",
    "ibm_sales_cloud_ref": "IBM-OPP-2025-088431",
    "registered_at":       "2025-07-21T10:00:00Z"
  }
}
```

**Consumer:** `vpcp-deal-agent` (triggers co-sell proposal drafting via LiteLLM).

#### `i3.vpcp.deal.conflict_flagged`

Emitted when `check_deal_conflict` detects an overlap.

```json
{
  "specversion": "1.0",
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "source": "vpcp-core-api",
  "type": "i3.vpcp.deal.conflict_flagged",
  "time": "2025-07-21T09:00:00Z",
  "tenantid": "a1b2c3d4-0000-0000-0000-000000000001",
  "datacontenttype": "application/json",
  "partitionkey": "d1b2c3d4-0000-0000-0000-000000000003",
  "data": {
    "deal_id":             "d1b2c3d4-0000-0000-0000-000000000003",
    "tenant_id":           "a1b2c3d4-0000-0000-0000-000000000001",
    "conflicting_deal_id": "e1b2c3d4-0000-0000-0000-000000000004",
    "customer_account":    "Acme Corporation Kenya",
    "product_family":      "watsonx",
    "conflict_window_days": 90
  }
}
```

**Consumer:** Commercial desk notification service.

#### `i3.vpcp.partner.onboarded`

Emitted when a new partner is created via `POST /v1/partners`.

```json
{
  "specversion": "1.0",
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "source": "vpcp-core-api",
  "type": "i3.vpcp.partner.onboarded",
  "time": "2025-07-21T08:00:00Z",
  "tenantid": "a1b2c3d4-0000-0000-0000-000000000001",
  "datacontenttype": "application/json",
  "partitionkey": "b1b2c3d4-0000-0000-0000-000000000002",
  "data": {
    "partner_id":          "b1b2c3d4-0000-0000-0000-000000000002",
    "tenant_id":           "a1b2c3d4-0000-0000-0000-000000000001",
    "organisation_name":   "AfroTech Resellers Ltd",
    "tier":                "gold",
    "country_code":        "KE",
    "ibm_partner_id":      "PW-00123456"
  }
}
```

**Consumer:** CRM enrichment agent (`crm-enrichment-agent`).

### 5.4 Kafka ACL Map (Strimzi KafkaUser)

| Principal            | Topic                        | Operation         |
|----------------------|------------------------------|-------------------|
| `vpcp-core-api`      | `i3.vpcp.deal.events`        | Write             |
| `vpcp-core-api`      | `i3.vpcp.partner.events`     | Write             |
| `vpcp-deal-agent`    | `i3.vpcp.deal.events`        | Read              |
| `crm-enrichment-agent` | `i3.vpcp.partner.events`   | Read              |
| `commercial-desk-svc` | `i3.vpcp.deal.events`       | Read              |

---

## 6. Temporal Worker Deployment Spec

```yaml
# Worker pod (runs inside i3-vpcp-core namespace)
env:
  TEMPORAL_HOST:        temporal-frontend.i3-vpcp-core.svc:7233
  TEMPORAL_NAMESPACE:   vpcp-deals
  TEMPORAL_TASK_QUEUE:  vpcp-deal-registration
  MCP_GATEWAY_URL:      http://mcp-gateway.i3-agent-mesh.svc.cluster.local:8000
  VPCP_DEAL_AGENT_ID:   vpcp-deal-agent
  # Secrets injected from OpenBao via ExternalSecrets:
  VPCP_AGENT_JWT:       <from i3/vpcp/agent-jwt>
  DATABASE_URL:         <from i3/vpcp/db-url>
  KAFKA_BOOTSTRAP:      <from i3/vpcp/kafka-bootstrap>
```

---

## 7. HC Compliance Matrix

| Constraint | Implementation                                                          | Status |
|------------|-------------------------------------------------------------------------|--------|
| HC-3       | Commercial desk signal (`commercial_desk_approved`) is the only way to advance past Step 2. vpcp-deal-agent (L1) CANNOT self-approve. | ✅ |
| HC-4       | `DealRequest.__post_init__` rejects missing `tenant_id`. All activities propagate it. All CloudEvents carry `tenantid`. | ✅ |
| HC-5       | `mcp_sync_to_ibm_sales_cloud` POSTs to MCP Gateway only. Direct IBM API calls are forbidden. `vpcp-deal-agent` manifest marks `vpcp.ibm_sales_cloud.sync` Tier 3. | ✅ |
| HC-7       | No `DEV_BYPASS_AUTH` in any workflow file or env template.              | ✅ |
