# MCP Tool Contract — `kafka_event_publish`

**Contract version:** 1.0  
**Status:** APPROVED — wraps the canonical `_build_cloud_event` + `AIOKafkaProducer.send_and_wait` pattern; enforces 9-field envelope before any agent can write to a Kafka topic  
**Hard-constraint refs:** HC-4, HC-5  
**Upstream implementation:** [`platform/engage/consumers/kafka_consumers.py:_build_cloud_event()`](../../platform/engage/consumers/kafka_consumers.py) · AIOKafka producer pattern (lines 526–529) · Strimzi KRaft cluster at `kafka-bootstrap.i3-messaging.svc.cluster.local:9092`

---

## 1. Purpose

Provides a **validated, audited Kafka publish** as a first-class MCP tool so that agents propose event publication without ever holding a Kafka bootstrap URL, SASL credential, or producing directly to the broker.

The canonical producer pattern in [`kafka_consumers.py`](../../platform/engage/consumers/kafka_consumers.py) already enforces the 9-field CloudEvent envelope. This tool exposes that pattern through the gateway so:

1. Agents submit a `data` payload and metadata — the gateway builds and signs the compliant CloudEvent.
2. The gateway validates all 9 fields before sending — a malformed envelope is rejected with `HTTP 422`.
3. The topic allowlist (enforced by the gateway) prevents agents from publishing to topics outside their declared permission set.
4. Every publish emits a separate audit event, creating a durable proposal trail (HC-5: agents propose, policy disposes).

---

## 2. Tool Registration Block

```yaml
name: kafka_event_publish
version: "1.0"
risk_tier: 1              # reversible_write — Kafka messages can be consumed or ignored; not directly user-facing
side_effect_class: reversible_write
requires_human_gate: false   # L1 agents may publish to pre-approved topics without a human gate
tenant_scoped: true           # HC-4: tenantid injected into every CloudEvent envelope
autonomy_level: L1            # HC-3: L1 is the ceiling for direct Kafka writes
```

> **Note on `requires_human_gate`:** The gateway enforces a per-topic approval policy. Topics classified as `execute-gated` in the topic registry (e.g. `engage.campaign-trigger`) require a confirmation token issued by a prior `propose` step. The `requires_human_gate` flag at the tool level is `false` because the gate is enforced at the topic level, not the tool level.

---

## 3. Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "topic",
    "event_type",
    "subject",
    "data",
    "tenant_id",
    "caller_agent_id",
    "correlation_id"
  ],
  "additionalProperties": false,
  "properties": {
    "topic": {
      "type": "string",
      "enum": [
        "engage.email-events",
        "engage.sms-events",
        "engage.send-queue",
        "engage.whatsapp-events",
        "engage.campaign-trigger",
        "engage.ai-personalize",
        "i3.decisions.log",
        "i3.consent.events"
      ],
      "description": "Target Kafka topic. Must be in the gateway-managed allowlist. Topics not in this enum are rejected with HTTP 403."
    },
    "event_type": {
      "type": "string",
      "pattern": "^i3\\.[a-z0-9-]+\\.[a-z0-9-]+\\.[a-z0-9-]+$",
      "description": "CloudEvent type in reverse-DNS dot notation. Must match pattern i3.<domain>.<entity>.<verb>."
    },
    "subject": {
      "type": "string",
      "maxLength": 256,
      "description": "CloudEvent subject — resource path, e.g. campaign/abc123."
    },
    "data": {
      "type": "object",
      "description": "Domain payload dict. Must not contain raw NIDs, phone numbers, or plaintext passwords (HC-6). Validated by gateway schema registry lookup keyed on event_type."
    },
    "tenant_id": {
      "type": "string",
      "format": "uuid",
      "description": "HC-4: Caller tenant UUID. Injected into the tenantid CloudEvent field."
    },
    "caller_agent_id": {
      "type": "string",
      "description": "Registered agent ID from the Agent Registry."
    },
    "correlation_id": {
      "type": "string",
      "description": "UUIDv7 from the caller's active request context. Injected into data.correlation_id."
    },
    "causation_id": {
      "type": "string",
      "description": "Optional: the id of the upstream CloudEvent that caused this one."
    },
    "idempotency_key": {
      "type": "string",
      "description": "Optional: caller-supplied key for deduplication. If a message with this key was published within the last 5 minutes, the gateway returns the original audit_event_id without re-publishing."
    }
  }
}
```

---

## 4. Output Schema

### 4a. Published successfully

```json
{
  "published": true,
  "event_id": "<uuidv7>",
  "topic": "engage.email-events",
  "offset": 104312,
  "partition": 2,
  "audit_event_id": "<uuidv7>"
}
```

### 4b. Idempotency hit (duplicate suppressed)

```json
{
  "published": false,
  "reason": "duplicate_suppressed",
  "original_event_id": "<uuidv7>",
  "audit_event_id": "<uuidv7>"
}
```

### 4c. Topic gate blocked (confirmation token required)

```json
{
  "published": false,
  "reason": "topic_gate_required",
  "confirmation_token": "<opaque-token>",
  "expires_at": "<rfc3339+30s>",
  "audit_event_id": "<uuidv7>"
}
```

> For gated topics (e.g. `engage.campaign-trigger`), the caller receives a `confirmation_token`. The caller must present this token to `kafka_event_confirm` within 30 seconds. This implements the HC-5 "agents propose, policy disposes" pattern.

### 4d. Validation failure

```json
{
  "published": false,
  "reason": "envelope_invalid",
  "missing_fields": ["tenantid"],
  "audit_event_id": "<uuidv7>"
}
```

> HTTP status `422 Unprocessable Entity`.

---

## 5. Authentication

| Layer | Mechanism |
|---|---|
| Agent → Gateway | Keycloak Bearer JWT (RS256) issued to the registered agent service account |
| Gateway → Kafka | SASL/SCRAM-SHA-512 using credentials from OpenBao at `i3/kafka/producer-sa-secret`; connection uses TLS with Strimzi-issued CA cert |
| Topic-level ACL | Strimzi Kafka User resource grants `WRITE` only to the `mcp-gateway-producer` principal |

The calling agent **never** receives the Kafka bootstrap URL, SASL credentials, or CA certificate. This satisfies **Rule R2**.

---

## 6. Tenant Context

`tenant_id` is:
1. Validated against the JWT's `tenant_id` claim — mismatches cause `HTTP 403`
2. Injected into the `tenantid` CloudEvent field — **the gateway enforces this; agent-supplied `tenantid` inside `data` is ignored**
3. Logged in every audit event (HC-4)

---

## 7. Idempotency

**Supported via `idempotency_key`.** When provided:
- The gateway maintains a Redis set (`mcp:kafka-pub:idem:<idempotency_key>`) with a 5-minute TTL
- Duplicate detection window: **5 minutes**
- A duplicate call returns `published: false / reason: duplicate_suppressed` and the original `event_id`

When `idempotency_key` is absent, no deduplication is applied; each call produces a new message.

The underlying Kafka producer uses `enable.idempotence=true` at the broker level for exactly-once partition-level guarantees (Strimzi KRaft cluster, [`kafka-kraft.yaml:76`](../../platform/operators/kafka/kafka-kraft.yaml)).

---

## 8. Approval Requirement

| Topic | Gate type | Mechanism |
|---|---|---|
| `engage.email-events` | **None** | Direct publish |
| `engage.sms-events` | **None** | Direct publish |
| `engage.send-queue` | **None** | Direct publish |
| `engage.whatsapp-events` | **None** | Direct publish |
| `engage.ai-personalize` | **None** | Direct publish |
| `engage.campaign-trigger` | **2-stage gate** | Returns `confirmation_token`; agent must call `kafka_event_confirm` |
| `i3.decisions.log` | **None** | Direct publish |
| `i3.consent.events` | **2-stage gate** | Returns `confirmation_token`; required for any consent mutation proposal |

---

## 9. CloudEvent Envelope Built by Gateway

The gateway calls the equivalent of [`_build_cloud_event()`](../../platform/engage/consumers/kafka_consumers.py) with all 9 required fields:

```json
{
  "specversion": "1.0",
  "id": "<uuidv7-generated-by-gateway>",
  "source": "i3/mcp-gateway/kafka-event-publish",
  "type": "<caller-supplied event_type>",
  "datacontenttype": "application/json",
  "time": "<rfc3339-utc-now>",
  "tenantid": "<jwt-tenant-uuid>",
  "subject": "<caller-supplied subject>",
  "data": {
    "<caller-supplied data fields>",
    "correlation_id": "<caller-correlation-id>",
    "causation_id": "<caller-causation-id>",
    "actor": "<jwt-sub>"
  }
}
```

The `id` is always a **UUIDv7** generated by the gateway. Callers may not supply their own `id`.

---

## 10. Audit Event Emitted on Call

Every invocation — published, suppressed, or gated — emits one CloudEvent to topic `i3.mcp.kafka.published`:

```json
{
  "specversion": "1.0",
  "id": "<uuidv7>",
  "source": "i3/mcp-gateway/kafka-event-publish",
  "type": "i3.mcp.kafka.published",
  "datacontenttype": "application/json",
  "time": "<rfc3339-utc>",
  "tenantid": "<caller-tenant-uuid>",
  "subject": "topic/<topic>",
  "data": {
    "published": true,
    "event_id": "<uuidv7>",
    "topic": "engage.email-events",
    "event_type": "i3.engage.email.queued",
    "caller_agent_id": "<agent-id>",
    "correlation_id": "<caller-correlation-id>",
    "idempotency_key": "<key-or-null>"
  }
}
```

> `data.data` (the domain payload) is **never** included in the audit event — only routing metadata. This prevents PII leakage through the audit topic.

---

## 11. Timeout & Retry Policy

| Parameter | Value | Rationale |
|---|---|---|
| Kafka `send_and_wait` timeout | **10 s** | Matches Strimzi cluster ack timeout for `acks=all` |
| Gateway total timeout | **12 s** | Includes schema validation + producer lifecycle |
| Client timeout | **15 s** | Agent budget |
| Retry policy | **2 retries, 500 ms exponential backoff** | `idempotency_key` must be supplied by caller if retrying to prevent duplicates |
| Circuit breaker | **Open after 3 consecutive failures in 30 s** | Returns `published: false / reason: broker_unavailable`; agents buffer and retry with backoff |

---

## 12. Upstream Credentials Wrapped

| Secret | OpenBao path | Scope |
|---|---|---|
| Kafka SASL password | `i3/kafka/producer-sa-secret` | MCP Gateway pod only; Strimzi `mcp-gateway-producer` principal |
| Kafka CA cert | Mounted from Strimzi `kafka-cluster-ca-cert` Secret | Gateway pod only; `rejectUnauthorized: true` enforced |
| Redis connection string (idempotency store) | `i3/redis/mcp-gateway-url` | Gateway pod only |

No raw Kafka credential or bootstrap URL is passed to any calling agent. This satisfies **Rule R2**.

---

## 13. Topic Allowlist Governance

Adding a new topic to the allowlist requires:
1. A `KafkaTopic` resource in [`platform/operators/kafka/kafka-kraft.yaml`](../../platform/operators/kafka/kafka-kraft.yaml) with retention and replication config
2. A Strimzi `KafkaUser` ACL granting `WRITE` to the `mcp-gateway-producer` principal
3. An update to the `topic` enum in this contract (§3 Input Schema)
4. A new topic gate classification entry in the gateway's topic policy table (§8)

No agent may publish to a topic that is not in the allowlist, regardless of Kafka ACL.
