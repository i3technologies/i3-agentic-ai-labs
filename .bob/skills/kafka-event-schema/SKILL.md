---
name: kafka-event-schema
description: Validates, generates, and evolves Kafka CloudEvent schemas for the i3 platform. Enforces HC-4 (tenantid), the 9-field envelope, and CloudEvent spec version 1.0. Use when authoring new event types, validating existing payloads, or evolving schema versions across services.
---

When the user needs to create, validate, or evolve a Kafka CloudEvent:

## 1. The 9-Field Mandatory Envelope

Every Kafka event on the i3 platform MUST carry ALL 9 fields. HC-4 makes `tenantid` non-negotiable.

| Field | Type | Rule | Example |
|-------|------|------|---------|
| `specversion` | string | Always `"1.0"` | `"1.0"` |
| `id` | string (UUIDv7) | Unique per event, time-ordered | `"0192a1b2-..."` |
| `source` | URI string | `"i3/<service-name>"` | `"i3/admissions-agent"` |
| `type` | string | Reverse-DNS dot notation | `"i3.admissions.application.created"` |
| `datacontenttype` | string | Always `"application/json"` | `"application/json"` |
| `time` | RFC3339 UTC | ISO 8601 with Z suffix | `"2025-07-01T12:00:00Z"` |
| `tenantid` | UUID string | **HC-4: never null/absent** | `"00000000-0000-0000-0000-000000000001"` |
| `subject` | string | `"<entity>/<id>"` | `"application/abc-123"` |
| `data` | object | Domain payload | `{ "applicantName": "...", ... }` |

Use `verify_cloudevent_envelope` MCP tool to validate any event dict programmatically.

## 2. Event Type Naming Convention

Format: `i3.<domain>.<entity>.<verb>`

| Domain | Example Types |
|--------|--------------|
| admissions | `i3.admissions.application.created`, `i3.admissions.application.approved` |
| pmaas | `i3.pmaas.campaign.briefing.generated`, `i3.pmaas.campaign.content.requested` |
| engage | `i3.engage.email.queued`, `i3.engage.sms.sent` |
| consent | `i3.consent.record.created`, `i3.consent.record.revoked` |
| grading | `i3.grading.submission.received`, `i3.grading.result.published` |

## 3. Python Producer Template

```python
import uuid
from datetime import datetime, UTC
from aiokafka import AIOKafkaProducer
import json

async def emit_event(
    producer: AIOKafkaProducer,
    topic: str,
    event_type: str,
    subject: str,
    tenant_id: str,
    data: dict,
) -> None:
    """Emit a HC-4 compliant CloudEvent to Kafka."""
    event = {
        "specversion": "1.0",
        "id": str(uuid.uuid7()),          # UUIDv7 for time-ordering
        "source": "i3/<service-name>",
        "type": event_type,
        "datacontenttype": "application/json",
        "time": datetime.now(UTC).isoformat(),
        "tenantid": tenant_id,            # HC-4: never absent
        "subject": subject,
        "data": data,
    }
    await producer.send_and_wait(
        topic,
        value=json.dumps(event).encode("utf-8"),
        key=tenant_id.encode("utf-8"),    # partition by tenant
    )
```

## 4. TypeScript Producer Template

```typescript
import { v7 as uuidv7 } from "uuid";
import { Producer } from "kafkajs";

async function emitEvent(
  producer: Producer,
  topic: string,
  eventType: string,
  subject: string,
  tenantId: string,   // HC-4: caller must supply
  data: Record<string, unknown>
): Promise<void> {
  const event = {
    specversion: "1.0",
    id: uuidv7(),
    source: "i3/<service-name>",
    type: eventType,
    datacontenttype: "application/json",
    time: new Date().toISOString(),
    tenantid: tenantId,   // HC-4
    subject,
    data,
  };
  await producer.send({
    topic,
    messages: [{ key: tenantId, value: JSON.stringify(event) }],
  });
}
```

## 5. Schema Evolution Rules

When evolving an existing event schema:

| Change | Allowed? | Strategy |
|--------|---------|---------|
| Add optional field to `data` | ✅ Yes | Consumers must ignore unknown fields |
| Remove field from `data` | ⚠️ Breaking | Bump event type version: `i3.admissions.application.created.v2` |
| Change field type | ❌ Never | Create new event type |
| Change `tenantid` cardinality | ❌ Never | HC-4 — always UUID NOT NULL |
| Change `specversion` | ❌ Never | Always `"1.0"` |

Consumer Pydantic models must use `model_config = ConfigDict(extra="ignore")` to survive additive changes.

## 6. Validation Checklist

Before publishing a new event type to staging:
- [ ] All 9 fields present in payload
- [ ] `tenantid` is a valid UUID (use `verify_cloudevent_envelope` MCP tool)
- [ ] `type` follows `i3.<domain>.<entity>.<verb>` naming convention
- [ ] `id` is UUIDv7 (not UUIDv4) for time-ordered deduplication
- [ ] Producer partitions by `tenantId` key
- [ ] Corresponding Pydantic consumer model exists with `extra="ignore"`
- [ ] New topic added to `platform/operators/kafka/kafka-kraft.yaml` topic list
