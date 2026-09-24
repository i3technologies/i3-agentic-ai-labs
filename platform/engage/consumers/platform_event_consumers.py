"""
i3 Platform — Core Event Producers & Consumers (FIX-09)

Covers the four topics that had KafkaTopic CRDs but no application code:
  1. admissions-leads      → produced by admissions-agent, consumed here for CRM sync
  2. evalos-submissions    → produced by evalos-web, consumed here for grading pipeline
  3. ott-stream-events     → produced by OTT service, consumed here for billing/analytics
  4. ai-lab-usage          → produced by LiteLLM gateway, consumed here for quota tracking

All messages use the 9-field CloudEvent envelope (FIX-01 / FIX-11):
  specversion, id (UUIDv7), source, type (i3.<domain>.<entity>.<verb>),
  datacontenttype, time, tenantid, subject, data.

HC-4: tenant_id UUID NOT NULL on every payload and DB write.
HC-6: no raw NID/phone in any event payload — HMAC-SHA256 hashes only.

Env vars:
  KAFKA_BOOTSTRAP     — kafka-bootstrap.i3-messaging.svc.cluster.local:9092
  ENGAGE_DB_URL / DATABASE_URL — PostgreSQL DSN
  MEMBER_HMAC_SECRET  — HC-6 HMAC key
"""

import os
import json
import logging
import asyncio
import uuid
from datetime import datetime, UTC

import asyncpg
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import BaseModel, Field, ValidationError, ConfigDict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka-bootstrap.i3-messaging.svc.cluster.local:9092")
DATABASE_URL    = os.getenv("ENGAGE_DB_URL", os.getenv("DATABASE_URL", ""))

# ── CloudEvent type constants (FIX-11) ─────────────────────────
CE_TYPE_ADMISSION_LEAD_CREATED    = "i3.admissions.lead.created"
CE_TYPE_EVALOS_SUBMISSION_RECEIVED = "i3.evalos.submission.received"
CE_TYPE_OTT_STREAM_STARTED        = "i3.ott.stream.started"
CE_TYPE_OTT_STREAM_ENDED          = "i3.ott.stream.ended"
CE_TYPE_AI_LAB_USAGE_RECORDED     = "i3.ai-lab.usage.recorded"

# ── Topic names ─────────────────────────────────────────────────
TOPIC_ADMISSIONS_LEADS    = "admissions-leads"
TOPIC_EVALOS_SUBMISSIONS  = "evalos-submissions"
TOPIC_OTT_STREAM_EVENTS   = "ott-stream-events"
TOPIC_AI_LAB_USAGE        = "ai-lab-usage"


# ── CloudEvent envelope builder (shared with kafka_consumers.py) ─
def _build_cloud_event(
    event_type: str,
    source: str,
    subject: str,
    tenant_id: str,
    data: dict,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    actor: str | None = None,
) -> dict:
    return {
        "specversion":     "1.0",
        "id":              str(uuid.uuid7()),
        "source":          source,
        "type":            event_type,
        "datacontenttype": "application/json",
        "time":            datetime.now(UTC).isoformat(),
        "tenantid":        tenant_id,    # HC-4
        "subject":         subject,
        "data": {
            **data,
            "correlation_id": correlation_id,
            "causation_id":   causation_id,
            "actor":          actor,
        },
    }


# ── Minimal CloudEvent envelope for consumption ─────────────────
class _CloudEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    specversion:     str
    id:              str
    source:          str
    type:            str
    datacontenttype: str = "application/json"
    time:            str
    tenantid:        str    # HC-4
    subject:         str
    data:            dict

    def correlation_id(self) -> str | None:
        return self.data.get("correlation_id")

    def actor(self) -> str | None:
        return self.data.get("actor")


# ── Domain payload models ────────────────────────────────────────

class AdmissionLeadData(BaseModel):
    """Payload for i3.admissions.lead.created (inside CloudEvent.data)."""
    model_config = ConfigDict(extra="ignore")

    lead_id:         str         # UUID
    tenant_id:       str         # UUID (HC-4)
    subject_id_hash: str         # HC-6: HMAC-SHA256 of applicant email/phone
    program:         str
    source_channel:  str         # e.g. "web-form", "referral", "social"
    created_at:      str         # ISO8601


class EvalosSubmissionData(BaseModel):
    """Payload for i3.evalos.submission.received (inside CloudEvent.data)."""
    model_config = ConfigDict(extra="ignore")

    submission_id:   str         # UUID
    exam_id:         str
    attempt_id:      str
    tenant_id:       str         # UUID (HC-4)
    subject_id_hash: str         # HC-6: HMAC-SHA256 of student email
    submitted_at:    str         # ISO8601
    answer_count:    int = 0


class OttStreamEventData(BaseModel):
    """Payload for i3.ott.stream.started / i3.ott.stream.ended."""
    model_config = ConfigDict(extra="ignore")

    stream_id:       str         # UUID
    tenant_id:       str         # UUID (HC-4)
    subject_id_hash: str         # HC-6: HMAC-SHA256 of viewer identity
    content_id:      str
    event_at:        str         # ISO8601
    duration_seconds: int | None = None  # populated on stream.ended


class AiLabUsageData(BaseModel):
    """Payload for i3.ai-lab.usage.recorded (inside CloudEvent.data)."""
    model_config = ConfigDict(extra="ignore")

    usage_id:        str         # UUID
    tenant_id:       str         # UUID (HC-4)
    subject_id_hash: str         # HC-6: HMAC-SHA256 of student identity
    model_id:        str         # e.g. "granite-4-nano"
    input_tokens:    int
    output_tokens:   int
    recorded_at:     str         # ISO8601


# ── asyncpg pool ────────────────────────────────────────────────
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=2, max_size=10, command_timeout=30)
    return _pool


def _parse_cloud_event(raw: bytes, expected_type: str, log: logging.Logger) -> _CloudEventEnvelope | None:
    try:
        envelope = _CloudEventEnvelope.model_validate_json(raw)
    except ValidationError as exc:
        log.error("invalid_cloudevent expected_type=%s error=%s", expected_type, exc)
        return None
    if envelope.type != expected_type:
        log.warning("unexpected_event_type got=%s expected=%s — processing anyway", envelope.type, expected_type)
    return envelope


# ═══════════════════════════════════════════════════════════════
# 1. Admissions Leads Consumer
# Consumes: admissions-leads
# Action:   inserts lead record into crm_leads table for CRM sync
# ═══════════════════════════════════════════════════════════════

async def run_admissions_leads_consumer(pool: asyncpg.Pool) -> None:
    log = logging.getLogger("admissions-leads")
    consumer = AIOKafkaConsumer(
        TOPIC_ADMISSIONS_LEADS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="admissions-leads-crm-sync",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log.info("Admissions leads consumer started")
    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_ADMISSION_LEAD_CREATED, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                lead = AdmissionLeadData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_admission_lead_data error=%s", exc)
                await consumer.commit()
                continue

            try:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        # HC-4: set RLS context
                        await conn.execute("SET LOCAL app.tenant_id = $1", lead.tenant_id)
                        await conn.execute(
                            """INSERT INTO crm_leads
                                   (id, tenant_id, subject_id_hash, program, source_channel,
                                    created_at, cloudevent_id, correlation_id)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                               ON CONFLICT (id) DO NOTHING""",
                            lead.lead_id,
                            lead.tenant_id,
                            lead.subject_id_hash,   # HC-6
                            lead.program,
                            lead.source_channel,
                            lead.created_at,
                            envelope.id,
                            envelope.correlation_id(),
                        )
                await consumer.commit()
                log.info("admissions_lead_synced lead_id=%s tenant=%s", lead.lead_id, lead.tenant_id)
            except Exception as exc:
                log.error("admissions_lead_db_failed lead_id=%s: %s — not committing", lead.lead_id, exc)
    finally:
        await consumer.stop()


# ═══════════════════════════════════════════════════════════════
# 2. EvalOS Submissions Consumer
# Consumes: evalos-submissions
# Action:   triggers grading pipeline via HTTP to grading-service
# ═══════════════════════════════════════════════════════════════

GRADING_SERVICE_URL = os.getenv(
    "GRADING_SERVICE_URL",
    "http://grading-service.i3-evalos.svc.cluster.local:8080",
)


async def run_evalos_submissions_consumer(pool: asyncpg.Pool) -> None:
    log = logging.getLogger("evalos-submissions")
    consumer = AIOKafkaConsumer(
        TOPIC_EVALOS_SUBMISSIONS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="evalos-submissions-grading",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log.info("EvalOS submissions consumer started")

    import httpx  # local import to avoid top-level dep for modules that don't use it

    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_EVALOS_SUBMISSION_RECEIVED, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                submission = EvalosSubmissionData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_evalos_submission_data error=%s", exc)
                await consumer.commit()
                continue

            try:
                async with httpx.AsyncClient(timeout=15) as http:
                    resp = await http.post(
                        f"{GRADING_SERVICE_URL}/grade",
                        json={
                            "submission_id":   submission.submission_id,
                            "exam_id":         submission.exam_id,
                            "attempt_id":      submission.attempt_id,
                            "tenant_id":       submission.tenant_id,
                            "subject_id_hash": submission.subject_id_hash,  # HC-6
                            "cloudevent_id":   envelope.id,
                            "correlation_id":  envelope.correlation_id(),
                        },
                        headers={"X-Tenant-Id": submission.tenant_id},
                    )
                    resp.raise_for_status()
                await consumer.commit()
                log.info(
                    "evalos_submission_graded submission_id=%s tenant=%s",
                    submission.submission_id, submission.tenant_id,
                )
            except Exception as exc:
                log.error(
                    "evalos_submission_grading_failed submission_id=%s: %s — not committing",
                    submission.submission_id, exc,
                )
    finally:
        await consumer.stop()


# ═══════════════════════════════════════════════════════════════
# 3. OTT Stream Events Consumer
# Consumes: ott-stream-events
# Action:   records viewing session for billing and analytics
# ═══════════════════════════════════════════════════════════════

async def run_ott_stream_consumer(pool: asyncpg.Pool) -> None:
    log = logging.getLogger("ott-stream-events")
    consumer = AIOKafkaConsumer(
        TOPIC_OTT_STREAM_EVENTS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="ott-stream-billing",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log.info("OTT stream events consumer started")
    try:
        async for msg in consumer:
            # Accept both stream.started and stream.ended
            envelope: _CloudEventEnvelope | None = None
            for expected_type in (CE_TYPE_OTT_STREAM_STARTED, CE_TYPE_OTT_STREAM_ENDED):
                try:
                    envelope = _CloudEventEnvelope.model_validate_json(msg.value)
                    break
                except ValidationError:
                    pass
            if envelope is None:
                log.error("invalid_ott_stream_event — committing")
                await consumer.commit()
                continue

            try:
                stream_event = OttStreamEventData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_ott_stream_data error=%s", exc)
                await consumer.commit()
                continue

            try:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute("SET LOCAL app.tenant_id = $1", stream_event.tenant_id)
                        await conn.execute(
                            """INSERT INTO ott_stream_sessions
                                   (stream_id, tenant_id, subject_id_hash, content_id,
                                    event_type, event_at, duration_seconds, cloudevent_id)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                               ON CONFLICT (stream_id, event_type) DO NOTHING""",
                            stream_event.stream_id,
                            stream_event.tenant_id,
                            stream_event.subject_id_hash,  # HC-6
                            stream_event.content_id,
                            envelope.type,
                            stream_event.event_at,
                            stream_event.duration_seconds,
                            envelope.id,
                        )
                await consumer.commit()
                log.info(
                    "ott_stream_recorded stream_id=%s type=%s tenant=%s",
                    stream_event.stream_id, envelope.type, stream_event.tenant_id,
                )
            except Exception as exc:
                log.error(
                    "ott_stream_db_failed stream_id=%s: %s — not committing",
                    stream_event.stream_id, exc,
                )
    finally:
        await consumer.stop()


# ═══════════════════════════════════════════════════════════════
# 4. AI Lab Usage Consumer
# Consumes: ai-lab-usage
# Action:   records token usage for quota enforcement and billing
# ═══════════════════════════════════════════════════════════════

async def run_ai_lab_usage_consumer(pool: asyncpg.Pool) -> None:
    log = logging.getLogger("ai-lab-usage")
    consumer = AIOKafkaConsumer(
        TOPIC_AI_LAB_USAGE,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="ai-lab-usage-quota",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log.info("AI Lab usage consumer started")
    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_AI_LAB_USAGE_RECORDED, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                usage = AiLabUsageData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_ai_lab_usage_data error=%s", exc)
                await consumer.commit()
                continue

            try:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute("SET LOCAL app.tenant_id = $1", usage.tenant_id)
                        await conn.execute(
                            """INSERT INTO ai_lab_usage_log
                                   (id, tenant_id, subject_id_hash, model_id,
                                    input_tokens, output_tokens, recorded_at, cloudevent_id)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                               ON CONFLICT (id) DO NOTHING""",
                            usage.usage_id,
                            usage.tenant_id,
                            usage.subject_id_hash,  # HC-6
                            usage.model_id,
                            usage.input_tokens,
                            usage.output_tokens,
                            usage.recorded_at,
                            envelope.id,
                        )
                        # Update running quota counter for tenant
                        await conn.execute(
                            """INSERT INTO ai_lab_quota_counters (tenant_id, total_tokens, updated_at)
                               VALUES ($1, $2, NOW())
                               ON CONFLICT (tenant_id) DO UPDATE
                                 SET total_tokens = ai_lab_quota_counters.total_tokens + $2,
                                     updated_at   = NOW()""",
                            usage.tenant_id,
                            usage.input_tokens + usage.output_tokens,
                        )
                await consumer.commit()
                log.info(
                    "ai_lab_usage_recorded usage_id=%s tenant=%s model=%s tokens=%d",
                    usage.usage_id, usage.tenant_id, usage.model_id,
                    usage.input_tokens + usage.output_tokens,
                )
            except Exception as exc:
                log.error(
                    "ai_lab_usage_db_failed usage_id=%s: %s — not committing",
                    usage.usage_id, exc,
                )
    finally:
        await consumer.stop()


# ═══════════════════════════════════════════════════════════════
# Async main
# ═══════════════════════════════════════════════════════════════

async def _async_main(enabled: set) -> None:
    log = logging.getLogger("platform-events-main")
    pool = await get_pool()
    log.info("asyncpg pool ready")

    tasks = []
    if "admissions" in enabled:
        tasks.append(asyncio.create_task(run_admissions_leads_consumer(pool), name="admissions-leads"))
    if "evalos" in enabled:
        tasks.append(asyncio.create_task(run_evalos_submissions_consumer(pool), name="evalos-submissions"))
    if "ott" in enabled:
        tasks.append(asyncio.create_task(run_ott_stream_consumer(pool), name="ott-stream"))
    if "ai-lab" in enabled:
        tasks.append(asyncio.create_task(run_ai_lab_usage_consumer(pool), name="ai-lab-usage"))

    try:
        await asyncio.gather(*tasks)
    finally:
        await pool.close()


if __name__ == "__main__":
    import signal

    consumers_env = os.getenv("CONSUMERS", "admissions,evalos,ott,ai-lab")
    enabled = {c.strip() for c in consumers_env.split(",")}

    def handle_sigterm(*_):
        logging.getLogger("platform-events-main").info("SIGTERM received")

    signal.signal(signal.SIGTERM, handle_sigterm)
    asyncio.run(_async_main(enabled))
