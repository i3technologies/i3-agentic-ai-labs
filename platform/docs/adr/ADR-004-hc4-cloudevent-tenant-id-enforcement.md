# ADR-004: HC-4 CloudEvent `tenant_id` Enforcement Across All 9 Kafka Topics

**Status:** Proposed  
**Date:** 2026-09-22  
**Deciders:** i3 Platform Engineering Lead, Data Architect, Messaging/Events Lead  
**Relates to:** EXPLORE-GATE §8 (Event Catalogue), §13 Track D (D-2), U-08, HC-4  
**Supersedes:** — (no prior event schema ADR)

---

## Context

### Problem Statement

The i3 AI Platform operates 9 Kafka topics across 4 producer services. The EXPLORE-GATE audit
(2026-09-22) found that **zero of the 9 topics have a confirmed `tenant_id` field in their
CloudEvent envelope** — U-08 (Severity: High).

| Topic | Type | Producer | Consumer | HC-4 Status |
|-------|------|----------|---------|-------------|
| `engage.email-events` | `com.i3.engage.email.send` | Engage Web | Engage Consumer | ⚠️ Not confirmed |
| `engage.sms-events` | `com.i3.engage.sms.send` | Engage Web | Engage Consumer | ⚠️ Not confirmed |
| `engage.ai-personalize` | `com.i3.engage.ai.personalize` | Engage Web | Engage Consumer | ⚠️ Not confirmed |
| `engage.campaign-trigger` | `com.i3.engage.campaign.trigger` | Campaign Agent | Engage Consumer | ⚠️ Not confirmed |
| `engage.ai-personalize.dlq` | DLQ | Engage Consumer | **None** | N/A |
| `admissions-leads` | `com.i3.admissions.lead` | FORD API | Admissions Agent | ⚠️ Not confirmed |
| `evalos-submissions` | `com.i3.evalos.submission` | EvalOS Web | **None confirmed** | N/A |
| `ai-lab-usage` | `com.i3.ailab.usage` | AI Lab | **None confirmed** | N/A |
| `ott-stream-events` | `com.i3.ott.stream` | OTT | **None confirmed** | N/A |

Additionally, 5 of 9 topics have **no confirmed consumer** (EXPLORE-GATE §2.2, R-05).

Missing `tenant_id` in CloudEvent envelopes creates:
1. **HC-4 violation**: Messages cannot be attributed to a tenant, breaking the platform's
   multi-tenancy guarantee in the async communication layer.
2. **Consumer isolation failure**: Consumers that process messages and write to PostgreSQL
   (which has RLS enforced via `app.tenant_id`) will fail to set the correct RLS context if
   the message carries no `tenant_id`.
3. **Audit gap**: The `agent_decision_log` and consent audit tables cannot correlate async events
   to tenants without `tenant_id` in the Kafka envelope.

---

## Decision

**Enforce the CloudEvent 1.0 specification envelope with a mandatory `tenant_id` extension
attribute on all 9 Kafka topics, validated at both producer and consumer with Pydantic models.**

### CloudEvent Envelope Standard

Every Kafka message on every i3 topic MUST conform to this envelope:

```json
{
  "specversion": "1.0",
  "id": "<uuid4>",
  "source": "/services/{producer_service}",
  "type": "com.i3.{domain}.{entity}.{verb}",
  "datacontenttype": "application/json",
  "time": "<ISO8601>",
  "tenant_id": "<UUID>",
  "data": { ... }
}
```

The `tenant_id` field is a **CloudEvent extension attribute** (not inside `data`). Placing it
at the envelope level allows Kafka consumer interceptors and monitoring tools to read tenant
context without deserialising the payload.

### Per-Topic Schema (Normative)

#### `engage.email-events`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/engage-web",
  "type": "com.i3.engage.email.send", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "send_job_id": "uuid",
    "to_email": "string",
    "subject": "string (max 998)",
    "html_body": "string",
    "from_name": "string",
    "from_email": "string"
  }
}
```

#### `engage.sms-events`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/engage-web",
  "type": "com.i3.engage.sms.send", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "send_job_id": "uuid",
    "to_phone": "E.164 string",
    "message": "string (max 1600)"
  }
}
```

#### `engage.ai-personalize`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/engage-web",
  "type": "com.i3.engage.ai.personalize", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "send_job_id": "uuid",
    "template": "string",
    "contact": { "name": "string", "email": "string", "metadata": "object" },
    "channel": "email | sms | whatsapp"
  }
}
```

#### `engage.campaign-trigger`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/campaign-agent",
  "type": "com.i3.engage.campaign.trigger", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "job_id": "uuid",
    "campaign_id": "integer",
    "send_job_id": "uuid",
    "triggered_at": "ISO8601",
    "retry_count": "integer (default 0)"
  }
}
```

#### `admissions-leads`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/ford-api",
  "type": "com.i3.admissions.lead", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "lead_id": "uuid",
    "member_token": "HMAC-SHA256 hex string (not raw NID — HC-6)",
    "programme_interest": "string",
    "source": "ussd | web | api"
  }
}
```

#### `evalos-submissions`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/evalos-web",
  "type": "com.i3.evalos.submission", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "attempt_id": "uuid",
    "exam_id": "uuid",
    "candidate_id": "uuid",
    "submitted_at": "ISO8601",
    "answer_count": "integer"
  }
}
```

#### `ai-lab-usage`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/ai-lab",
  "type": "com.i3.ailab.usage", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "session_id": "uuid",
    "notebook_id": "string",
    "model": "string",
    "input_tokens": "integer",
    "output_tokens": "integer",
    "cost_usd": "number"
  }
}
```

#### `ott-stream-events`
```json
{
  "specversion": "1.0", "id": "uuid", "source": "/services/ott",
  "type": "com.i3.ott.stream", "datacontenttype": "application/json",
  "time": "ISO8601", "tenant_id": "UUID",
  "data": {
    "stream_id": "uuid",
    "event_type": "started | stopped | error",
    "viewer_count": "integer",
    "duration_seconds": "integer"
  }
}
```

### Consumer Dead-Letter Policy

If a message arrives on any topic **without** a `tenant_id` in the envelope, the consumer MUST:
1. Log the malformed message with `error_type: missing_tenant_id`.
2. Produce the raw message to `{topic}.dlq` (dead-letter queue).
3. Commit the offset — **do not retry** a structurally invalid message.

### Producer Validation

All producers must validate the envelope against the Pydantic `CloudEventEnvelope` model before
producing. An invalid envelope (missing `tenant_id`) must raise a producer-side exception and
log to the DLQ topic, not silently drop.

---

## Alternatives Considered

### A1 — Include `tenant_id` inside `data` payload only (not envelope extension)
**Rejected.** CloudEvent extension attributes at the envelope level are readable by Kafka stream
processors and monitoring tools without deserialising `data`. Placing `tenant_id` inside `data`
breaks filtering in Kafka Streams, ksqlDB, and the Prometheus Kafka exporter.

### A2 — Use Kafka message headers instead of CloudEvent extension attributes
**Rejected.** Kafka headers are not a CloudEvent-native mechanism and require separate handling
at every consumer. CloudEvent extension attributes are the specified standard for additional
context metadata (CloudEvents spec §3.2).

### A3 — Use Apache Avro schema registry for envelope validation
**Deferred to Phase 4.** Schema registry adds operational complexity and requires Confluent Schema
Registry or Apicurio. The current Pydantic validation approach provides sufficient type safety
for Phase 2 without the overhead.

### A4 — Only add `tenant_id` to the 4 topics with confirmed consumers
**Rejected.** HC-4 is an unconditional platform invariant. All topics — including those with no
current consumer — must carry `tenant_id` so that future consumers are not required to
retroactively patch message schemas.

---

## Technical Drivers

| Driver | Detail |
|--------|--------|
| HC-4 compliance | `tenant_id` is mandatory on every Kafka event — this is a non-negotiable hard constraint |
| Consumer RLS correctness | PostgreSQL consumers set `app.tenant_id` from the envelope before executing SQL — correct tenancy in the DB layer depends on the envelope being correct |
| Observability | Prometheus Kafka lag metric can be broken down by `tenant_id` header once it is in the envelope |
| Forward compatibility | Schemas are versioned (`specversion: "1.0"`); future schema evolution follows CloudEvent spec §4 |

---

## Security Implications

| # | Implication |
|---|------------|
| SEC-1 | The `admissions-leads` topic carries a `member_token` — this MUST be the HMAC-SHA256 token (HC-6), not a raw national ID. The consumer validates `member_token` length and format as a hex string before processing. |
| SEC-2 | Kafka `engage.sms-events` carries `to_phone` in E.164 format. This is PII — the topic must be accessible only to the Engage Consumer service account (Kafka ACL: read-only for `i3-engage-consumer-sa`). |
| SEC-3 | Kafka topic ACLs: `engage.*` topics: producer = Engage Web SA only; consumer = Engage Consumer SA only. Cross-namespace access denied. |
| SEC-4 | DLQ messages may contain partial PII — DLQ topics must have same ACL restrictions as source topics. |

---

## Multi-Tenancy Implications

- **Strict envelope enforcement**: A message without `tenant_id` is routed to DLQ and never
  processed. This prevents implicit defaulting to a fallback tenant.
- **Consumer isolation**: Each Kafka consumer, before writing to PostgreSQL, executes
  `SET app.tenant_id = $1` using the envelope `tenant_id`. RLS then enforces read/write isolation.
- **Cross-tenant message delivery**: Impossible by construction — each message carries exactly
  one `tenant_id`; consumers write to exactly one tenant's data partition.

---

## Agent-Autonomy Implications

- HC-5: Campaign Agent's `kafka.produce` (Tier 2) tool call through the MCP gateway requires the
  `tenant_id` to be injected into the CloudEvent envelope by the gateway, not by the agent.
  This prevents an agent from forging a different tenant's `tenant_id`.
- HC-3: No autonomy level change.

---

## Data Implications

### Pydantic Base Model (shared across all producers/consumers)

```python
from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from typing import Any

class CloudEventEnvelope(BaseModel):
    specversion: str = Field("1.0", const=True)
    id: str = Field(..., description="UUID4 event identifier")
    source: str = Field(..., description="Producing service path, e.g. /services/engage-web")
    type: str = Field(..., description="com.i3.{domain}.{entity}.{verb}")
    datacontenttype: str = Field("application/json", const=True)
    time: datetime
    tenant_id: UUID4     # HC-4: mandatory extension attribute
    data: Any
```

### Consumer Validation Pattern

```python
# In every Kafka consumer handler:
try:
    envelope = CloudEventEnvelope.model_validate_json(msg.value)
except ValidationError as e:
    logger.error("invalid_cloudevent", topic=msg.topic, error=str(e))
    await dlq_producer.send(f"{msg.topic}.dlq", msg.value)
    # commit offset — do not retry
    continue

# Set RLS context
async with pool.acquire() as conn:
    await conn.execute("SET app.tenant_id = $1", str(envelope.tenant_id))
    # proceed with domain logic
```

---

## Event Implications

This ADR defines the event schema standard. It does not add new topics. The 5 topics with no
confirmed consumer (EXPLORE-GATE R-05) gain schema definitions in this ADR, which will accelerate
consumer implementation in Phase 3.

The `engage.ai-personalize.dlq` topic is promoted to a formal DLQ pattern — all topics gain a
corresponding `.dlq` topic for malformed message parking.

---

## Operational Implications

| Concern | Mitigation |
|---------|-----------|
| Schema migration for existing topics | Existing messages in-flight that predate the schema change will be rejected by the new consumer validation and routed to DLQ. A one-time DLQ review is required after cutover. |
| Producer migration | Engage Web TypeScript producers must be updated to include CloudEvent envelope fields. A migration PR is required per producer. |
| Consumer lag spike during cutover | DLQ routing is fast (no retries on invalid messages). Consumer lag should not spike. |
| Schema registry deferred | Pydantic validation is sufficient for Phase 2; no schema registry deployment required. |

---

## Performance Implications

| Aspect | Impact |
|--------|--------|
| Message size | CloudEvent envelope adds ~200 bytes per message. Negligible for current message volumes. |
| Pydantic validation overhead | ~0.5ms per message deserialization. Negligible at < 1000 messages/second. |
| DLQ routing | Invalid messages add one produce call to DLQ. No consumer retry loop overhead. |

---

## Cost Implications

- DLQ topics: minimal storage (Kafka topic replication ×3 of malformed messages only).
- No new infrastructure required.

---

## Rollback Strategy

1. **Consumer-side**: `CLOUDEVENT_VALIDATION=false` environment variable in Engage Consumer
   disables envelope validation. Consumers revert to raw JSON parsing. **This is a temporary
   escape hatch only** — do not leave disabled in production.
2. **Producer-side**: Reverting producer code to pre-envelope format requires a git revert PR.
   CloudEvent envelope fields are additive — old consumers ignore unknown fields if validation
   is off.
3. **DLQ**: Malformed messages in DLQ are not automatically re-processed. Manual operator
   intervention required for any DLQ replay.

---

## HC-1 through HC-8 Mapping

| Constraint | Mapping |
|-----------|---------|
| HC-1 | No change to solution-01 through solution-08 namespaces. |
| HC-2 | `admissions-leads` topic from FORD API must carry `tenant_id` before Fabric USSD flow is live — this ADR enforces it. |
| HC-3 | No autonomy tier change. |
| HC-4 | This ADR's primary purpose: `tenant_id UUID NOT NULL` in every CloudEvent envelope across all 9 topics. |
| HC-5 | MCP gateway injects `tenant_id` into CloudEvent envelope for agent-produced Kafka messages — agents cannot forge tenant context. |
| HC-6 | `admissions-leads.member_token` must be HMAC-SHA256 hex (not raw NID). Schema includes comment; consumer validates format. |
| HC-7 | No auth bypass. |
| HC-8 | No ballot data in Kafka events. FORD ballot choices go to Fabric `ballotPrivate` collection only. |

---

## Compliance / Statutory Mapping

| Requirement | How This ADR Satisfies It |
|------------|--------------------------|
| Kenya DPA 2019 §25 — lawful basis | `tenant_id` in envelope enables per-tenant consent check before PII processing in consumers |
| Kenya DPA 2019 §23 — data minimisation | Rejecting messages without `tenant_id` prevents inadvertent cross-tenant PII processing |
| IEBC Act Cap. 7A — voter data | FORD `admissions-leads` carries `member_token` (HMAC) not raw NID; HC-6 compliant |
| ISO 27001 A.12.4 — event logging | Every CloudEvent includes `id`, `time`, `source`, and `tenant_id` for complete audit trail |

---

## Acceptance Criteria

```
AC-1:  All 9 Kafka producers include specversion, id, source, type, time, tenant_id, data in every message
AC-2:  CloudEventEnvelope Pydantic model present in platform/engage/consumers/kafka_consumers.py
AC-3:  Consumer routes message without tenant_id to {topic}.dlq and commits offset (does not retry)
AC-4:  Consumer sets "SET app.tenant_id = $1" using envelope.tenant_id before any SQL write
AC-5:  admissions-leads producer: member_token is HMAC-SHA256 hex string, not raw national_id
AC-6:  engage.email-events: kubectl exec to Kafka → consume message → JSON contains top-level tenant_id field
AC-7:  DLQ topics exist for all 9 source topics (engage.email-events.dlq etc.)
AC-8:  Prometheus metric kafka_consumer_tenant_id_missing_total present, value 0 in steady state
AC-9:  CLOUDEVENT_VALIDATION flag absent from all production manifests (not just set to true)
AC-10: P2-GATE sensor: all 4 active consumers confirmed receiving messages with tenant_id in envelope
```

---

*Author: Bob (IBM Bob AI software engineer) | i3 AI Platform | 2026-09-22*  
*Do not implement until this ADR is reviewed and status changed to **Accepted** by Deciders.*
