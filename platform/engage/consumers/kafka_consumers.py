"""
i3-Engage Kafka Consumer Service.

Consumers:
  1. EmailEventConsumer       — engage.email-events     → update delivery/open/click status
  2. SMSEventConsumer         — engage.sms-events       → update SMS delivery status
  3. AIPersonalizeConsumer    — engage.ai-personalize   → generate personalised content via LiteLLM
  4. CampaignTrigger          — engage.campaign-trigger → schedule bulk sends via Brevo/Mailgun
  5. SendQueueConsumer        — engage.send-queue       → dispatch personalised messages (FIX-04)
  6. AiPersonaliseDLQConsumer — engage.ai-personalize.dlq → drain/audit DLQ

Env vars:
  KAFKA_BOOTSTRAP     — kafka-bootstrap.i3-messaging.svc.cluster.local:9092
  LITELLM_URL         — LiteLLM gateway
  LITELLM_KEY         — master key
  ENGAGE_DB_URL       — engage_db PostgreSQL connection  (was DATABASE_URL)
  DATABASE_URL        — alias kept for backward-compat
  BREVO_API_KEY       — Brevo (Sendinblue) API key for email
  MAILGUN_API_KEY     — Mailgun API key (fallback)
  MAILGUN_DOMAIN      — Mailgun domain
  MEMBER_HMAC_SECRET  — HC-6: keyed HMAC secret for subject_id hashing

Schema:
  All Kafka messages use the 9-field CloudEvent envelope (FIX-01 / FIX-11):
    specversion, id (UUIDv7), source, type (i3.<domain>.<entity>.<verb>),
    datacontenttype, time (RFC3339 UTC), tenantid, subject, data
"""

import os
import json
import logging
import asyncio
import re
import signal
import uuid
from datetime import datetime, UTC
from typing import Literal, Any

import asyncpg
import hashlib
import hmac as _hmac_mod
import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # FIX-10: replaced kafka-python
from pydantic import BaseModel, Field, ValidationError, ConfigDict

# Circuit-breaker for the consent-service (fail-closed, STEP-P2-02)
from platform.consent.circuit_breaker import consent_allowed as _cb_consent_allowed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

KAFKA_BOOTSTRAP    = os.getenv("KAFKA_BOOTSTRAP", "kafka-bootstrap.i3-messaging.svc.cluster.local:9092")
LITELLM_URL        = os.getenv("LITELLM_URL",     "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY        = os.getenv("LITELLM_KEY",     "")
# Prefer ENGAGE_DB_URL; fall back to DATABASE_URL for backward-compat
DATABASE_URL       = os.getenv("ENGAGE_DB_URL",   os.getenv("DATABASE_URL", ""))
BREVO_KEY          = os.getenv("BREVO_API_KEY",    "")
MAILGUN_KEY        = os.getenv("MAILGUN_API_KEY",  "")
MAILGUN_DOMAIN     = os.getenv("MAILGUN_DOMAIN",   "")
# Consent service (STEP-P2-02) — in-cluster DNS
CONSENT_SERVICE_URL = os.getenv(
    "CONSENT_SERVICE_URL",
    "http://consent-service.i3-consent.svc.cluster.local:8000",
)
# HC-6: HMAC secret for subject_id hashing — must be set in production
MEMBER_HMAC_SECRET = os.getenv("MEMBER_HMAC_SECRET", "")

MODEL_FAST          = os.getenv("LITELLM_MODEL_FAST", "qwen-fast")
AGENT_REGISTRY_URL  = os.getenv(
    "AGENT_REGISTRY_URL",
    "http://agent-registry.i3-agent-mesh.svc.cluster.local:8200",
)
AGENT_ID            = "engage-kafka-consumers-v1"
SERVICE_SOURCE      = "i3/engage-kafka-consumers"  # CloudEvent source (FIX-01)


# ── CloudEvent envelope builder (FIX-01 / FIX-11) ──────────────
# All Kafka messages produced by this service use this helper.

def _build_cloud_event(
    event_type: str,
    subject: str,
    tenant_id: str,
    data: dict,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    actor: str | None = None,
) -> dict:
    """Return a compliant 9-field CloudEvent envelope (specversion 1.0).

    Fields:
      specversion      — always "1.0"
      id               — UUIDv7 (time-ordered, FIX-12)
      source           — i3/engage-kafka-consumers
      type             — i3.<domain>.<entity>.<verb>  (FIX-11)
      datacontenttype  — application/json
      time             — RFC3339 UTC
      tenantid         — HC-4: caller-supplied UUID string
      subject          — <entity>/<id>
      data             — domain payload dict

    Extension attributes (carried in data envelope, not CE extensions,
    to remain compatible with the Pydantic consumer models):
      correlation_id, causation_id, actor
    """
    return {
        "specversion":     "1.0",
        "id":              str(uuid.uuid7()),   # time-ordered UUIDv7
        "source":          SERVICE_SOURCE,
        "type":            event_type,
        "datacontenttype": "application/json",
        "time":            datetime.now(UTC).isoformat(),
        "tenantid":        tenant_id,           # HC-4
        "subject":         subject,
        "data": {
            **data,
            "correlation_id": correlation_id,
            "causation_id":   causation_id,
            "actor":          actor,
        },
    }


# ── Pydantic consumer models (FIX-01: CloudEvent wrapper) ───────
# All incoming messages are expected to be wrapped in the CloudEvent
# envelope. The `data` field holds the domain payload validated below.
# ConfigDict(extra="ignore") allows additive schema evolution (skill §5).

class _CloudEventEnvelope(BaseModel):
    """Minimal CloudEvent envelope — validates the 9 required fields."""
    model_config = ConfigDict(extra="ignore")

    specversion:     str
    id:              str
    source:          str
    type:            str
    datacontenttype: str = "application/json"
    time:            str
    tenantid:        str   # HC-4
    subject:         str
    data:            dict

    def correlation_id(self) -> str | None:
        return self.data.get("correlation_id")

    def causation_id(self) -> str | None:
        return self.data.get("causation_id")

    def actor(self) -> str | None:
        return self.data.get("actor")


class EmailEventData(BaseModel):
    """Domain payload for i3.engage.email.queued (inside CloudEvent.data)."""
    model_config = ConfigDict(extra="ignore")

    send_job_id:      str
    subject_id_hash:  str   # HC-6: HMAC-SHA256 of email — raw address MUST NOT appear here
    email_subject:    str   = Field(..., max_length=998)
    html_body:        str
    from_name:        str   = Field(..., max_length=100)
    from_email:       str   = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    # Resolved delivery address carried separately for dispatch only — not stored in DB
    to_email:         str   = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    tenant_id:        str


class SmsEventData(BaseModel):
    """Domain payload for i3.engage.sms.queued (inside CloudEvent.data).

    FIX-02: raw to_phone replaced with subject_id_hash (HC-6).
    The resolved phone number is carried in to_phone_encrypted for
    dispatch only and must NOT be stored in the audit log.
    """
    model_config = ConfigDict(extra="ignore")

    send_job_id:       str
    subject_id_hash:   str   # HC-6: HMAC-SHA256(MEMBER_HMAC_SECRET, phone)
    to_phone_encrypted: str  # encrypted E.164 — for dispatch only, never logged/stored
    message:           str   = Field(..., max_length=1600)
    tenant_id:         str


class AiPersonaliseJobData(BaseModel):
    """Domain payload for i3.engage.ai-personalise.requested.

    FIX-03: subject_id_hash is now mandatory; raw email fallback removed.
    """
    model_config = ConfigDict(extra="ignore")

    template:         str
    contact:          dict   # must contain subject_id_hash (not raw email)
    send_job_id:      str
    channel:          Literal["email", "sms", "whatsapp"]
    tenant_id:        str

    def subject_id_hash(self) -> str:
        """Return the HMAC hash of the contact. Raises if absent (HC-6 enforcement)."""
        val = self.contact.get("subject_id_hash")
        if not val:
            raise ValueError(
                "contact.subject_id_hash is required (HC-6). "
                "Raw email/phone must not appear in AiPersonaliseJob payloads."
            )
        return val


class CampaignTriggerData(BaseModel):
    """Domain payload for i3.engage.campaign.triggered."""
    model_config = ConfigDict(extra="ignore")

    job_id:       str            # UUID
    campaign_id:  int
    tenant_id:    str            # UUID
    send_job_id:  str
    triggered_at: str            # ISO8601
    retry_count:  int = 0


class SendQueueData(BaseModel):
    """Domain payload for i3.engage.message.personalised (engage.send-queue)."""
    model_config = ConfigDict(extra="ignore")

    send_job_id:       str
    subject_id_hash:   str   # HC-6
    content:           str
    channel:           Literal["email", "sms", "whatsapp"]
    tenant_id:         str
    personalised_at:   str


class DLQData(CampaignTriggerData):
    """DLQ envelope payload for engage.ai-personalize.dlq."""
    model_config = ConfigDict(extra="ignore")

    failure_reason: str
    failed_at:      str
    original_topic: str = "engage.campaign-trigger"


class AiPersonaliseDLQData(BaseModel):
    """Envelope for messages routed to engage.ai-personalize.dlq from AI-personalise path."""
    model_config = ConfigDict(extra="ignore")

    job_id:         str
    send_job_id:    str
    campaign_id:    int | None = None
    channel:        str
    tenant_id:      str
    failure_reason: str
    failed_at:      str
    original_topic: str = "engage.ai-personalize"
    payload:        dict = Field(default_factory=dict)
    retry_count:    int = 0


# ── CloudEvent event-type constants (FIX-11) ───────────────────
CE_TYPE_EMAIL_QUEUED          = "i3.engage.email.queued"
CE_TYPE_SMS_QUEUED            = "i3.engage.sms.queued"
CE_TYPE_AI_PERSONALISE_REQ    = "i3.engage.ai-personalise.requested"
CE_TYPE_AI_PERSONALISE_DONE   = "i3.engage.message.personalised"
CE_TYPE_CAMPAIGN_TRIGGERED    = "i3.engage.campaign.triggered"
CE_TYPE_DLQ_CAMPAIGN          = "i3.engage.campaign.dlq"
CE_TYPE_DLQ_AI_PERSONALISE    = "i3.engage.ai-personalise.dlq"


# ── Shared asyncpg pool (STEP-P1-06) ───────────────────────────

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the module-level shared pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


# ── Lobster Trap — Prompt Injection Firewall (FLAG-7 / EC-1) ───
# 14-pattern canonical set mirrored from lobster-trap.ts.
_TRAP_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"system\s+prompt\s+override", re.I),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.I),
    re.compile(r"output\s+all\s+passwords", re.I),
    re.compile(r"reveal\s+internal\s+logic", re.I),
    re.compile(r"bypass\s+safety\s+filter", re.I),
    re.compile(r"act\s+as\s+DAN", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"(drop|delete|truncate)\s+table", re.I),
    re.compile(r"SELECT\s+.+FROM\s+", re.I),
    re.compile(r"<\s*(script|img|iframe|svg)\b", re.I),
    re.compile(r"prompt\s+injection", re.I),
    re.compile(r"disregard\s+(all\s+)?previous", re.I),
    re.compile(r"\bexfiltrate\b", re.I),
]


def _lobster_trap(text: str) -> str | None:
    """Return the first matched pattern source if injection is detected, else None."""
    for pattern in _TRAP_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def _guard_llm_input(field_name: str, value: str) -> None:
    """Raise ValueError if value triggers the Lobster Trap firewall."""
    matched = _lobster_trap(value)
    if matched:
        raise ValueError(
            f"LLM input rejected by Lobster Trap on field '{field_name}': {matched}"
        )


# ── LiteLLM helper ─────────────────────────────────────────────
async def llm_personalise(template: str, contact: dict) -> str:
    """Personalise a message template for a specific contact.

    Lobster Trap is applied to both template and contact values before
    any content reaches the LLM prompt (FLAG-7 / architecture-standards §Python).
    """
    _guard_llm_input("template", template)
    for k, v in contact.items():
        if isinstance(v, str):
            _guard_llm_input(f"contact.{k}", v)

    prompt = (
        f"You are Nuru, the i3-Engage AI personalisation engine.\n\n"
        f"Original message template:\n{template}\n\n"
        f"Contact details:\n{json.dumps(contact, default=str)}\n\n"
        f"Rewrite the message to be highly personalised for this specific contact. "
        f"Use their name, company, and any relevant context. "
        f"Keep the same core message and call-to-action. "
        f"Maximum 150 words. Return only the personalised message, no explanation."
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{LITELLM_URL}/chat/completions",
            json={
                "model":       MODEL_FAST,
                "messages":    [{"role": "user", "content": prompt}],
                "temperature": 0.6,
                "max_tokens":  300,
            },
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {LITELLM_KEY}",
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ── DB helper ──────────────────────────────────────────────────
async def update_contact_event(conn, contact_id: str, event_type: str, metadata: dict, tenant_id: str):
    # HC-4: set RLS context before INSERT (contact_events has tenant isolation via mig 003)
    await conn.execute("SET LOCAL app.tenant_id = $1", tenant_id)
    await conn.execute(
        """INSERT INTO contact_events (contact_id, event_type, metadata, tenant_id, created_at)
           VALUES ($1, $2, $3, $4, NOW())
           ON CONFLICT DO NOTHING""",
        contact_id, event_type, json.dumps(metadata), tenant_id,
    )


# ── CloudEvent parsing helper ───────────────────────────────────
def _parse_cloud_event(raw: bytes, expected_type: str, log: logging.Logger) -> _CloudEventEnvelope | None:
    """Parse raw bytes into a CloudEvent envelope. Returns None on any validation failure."""
    try:
        envelope = _CloudEventEnvelope.model_validate_json(raw)
    except ValidationError as exc:
        log.error("invalid_cloudevent expected_type=%s error=%s", expected_type, exc)
        return None
    if envelope.type != expected_type:
        log.warning(
            "unexpected_event_type got=%s expected=%s — processing anyway",
            envelope.type, expected_type,
        )
    return envelope


# ── Email Event Consumer ───────────────────────────────────────
# FIX-07: enable_auto_commit=False — offset committed only after durable DB write.
# FIX-13: partitioned by subject_id_hash for per-recipient ordering.
async def run_email_event_consumer(pool: asyncpg.Pool):
    log = logging.getLogger("email-events")
    consumer = AIOKafkaConsumer(
        "engage.email-events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-email-events",
        auto_offset_reset="earliest",
        enable_auto_commit=False,          # FIX-07: manual commit
    )
    await consumer.start()
    log.info("Email event consumer started (aiokafka, manual commit)")
    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_EMAIL_QUEUED, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                event = EmailEventData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_email_event_data error=%s", exc)
                await consumer.commit()
                continue

            log.info(
                "email_event send_job_id=%s tenant_id=%s correlation_id=%s",
                event.send_job_id, event.tenant_id, envelope.correlation_id(),
            )
            try:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await update_contact_event(
                            conn,
                            contact_id=event.subject_id_hash,   # HC-6: hash, not raw email
                            event_type="email_send",
                            metadata={
                                "send_job_id":    event.send_job_id,
                                "email_subject":  event.email_subject,
                                "tenant_id":      event.tenant_id,
                                "correlation_id": envelope.correlation_id(),
                                "actor":          envelope.actor(),
                            },
                            tenant_id=event.tenant_id,
                        )
                await consumer.commit()   # FIX-07: commit only after durable write
            except Exception as exc:
                log.error("email_event_db_failed send_job_id=%s: %s — not committing", event.send_job_id, exc)
                # Do NOT commit — message will be redelivered on restart
    finally:
        await consumer.stop()


# ── SMS Event Consumer ────────────────────────────────────────
# FIX-02: subject_id_hash replaces raw to_phone (HC-6).
# FIX-07: manual offset commit.
# FIX-13: partitioned by subject_id_hash.
async def run_sms_event_consumer(pool: asyncpg.Pool):
    log = logging.getLogger("sms-events")
    consumer = AIOKafkaConsumer(
        "engage.sms-events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-sms-events",
        auto_offset_reset="earliest",
        enable_auto_commit=False,          # FIX-07: manual commit
    )
    await consumer.start()
    log.info("SMS event consumer started (aiokafka, manual commit)")
    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_SMS_QUEUED, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                event = SmsEventData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_sms_event_data error=%s", exc)
                await consumer.commit()
                continue

            log.info(
                "sms_event send_job_id=%s tenant_id=%s correlation_id=%s",
                event.send_job_id, event.tenant_id, envelope.correlation_id(),
            )
            try:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute("SET LOCAL app.tenant_id = $1", event.tenant_id)
                        # FIX-02: Use subject_id_hash, never raw phone, for the audit record.
                        # to_phone_encrypted is used only for dispatch — not stored here.
                        await conn.execute(
                            """UPDATE sms_messages SET status = $1, updated_at = NOW()
                               WHERE provider_message_id = $2 AND tenant_id = $3""",
                            "sent",
                            event.send_job_id,
                            event.tenant_id,
                        )
                await consumer.commit()   # FIX-07
            except Exception as exc:
                log.error("sms_event_db_failed send_job_id=%s: %s — not committing", event.send_job_id, exc)
    finally:
        await consumer.stop()


# ── Consent gate helper (STEP-P2-02) ──────────────────────────
async def _consent_allowed(subject_id_hash: str, channel: str, purpose: str, tenant_id: str) -> bool:
    """Return True only when the consent-service confirms allowed=true.
    Routes through the shared circuit-breaker; fast-fails (default-deny) when
    the consent-service is unhealthy (HC-6 / DPA 2019 §25).
    """
    return await _cb_consent_allowed(subject_id_hash, channel, purpose, tenant_id)


# ── AI Personalise Consumer ────────────────────────────────────
# FIX-03: subject_id_hash is mandatory — raw email fallback removed.
# FIX-07: manual offset commit.
# FIX-08: 3-retry + DLQ path added (mirrors campaign-trigger pattern).

MAX_AI_PERSONALISE_RETRIES = 3
AI_PERSONALISE_TOPIC       = "engage.ai-personalize"
SEND_QUEUE_TOPIC           = "engage.send-queue"
AI_PERSONALISE_DLQ_TOPIC   = "engage.ai-personalize.dlq"


async def run_ai_personalise_consumer(pool: asyncpg.Pool):
    log = logging.getLogger("ai-personalise")
    consumer = AIOKafkaConsumer(
        AI_PERSONALISE_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-ai-personalise",
        auto_offset_reset="earliest",
        enable_auto_commit=False,          # FIX-07: manual commit
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await consumer.start()
    await producer.start()
    log.info("AI personalise consumer started (aiokafka, manual commit, DLQ=%s)", AI_PERSONALISE_DLQ_TOPIC)
    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_AI_PERSONALISE_REQ, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                job = AiPersonaliseJobData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_ai_personalise_data error=%s", exc)
                await consumer.commit()
                continue

            # FIX-03: subject_id_hash is mandatory — raises ValueError if absent
            try:
                subject_hash = job.subject_id_hash()
            except ValueError as exc:
                log.error("hc6_violation send_job_id=%s: %s", job.send_job_id, exc)
                await consumer.commit()
                continue

            # Consent gate (STEP-P2-02)
            if not await _consent_allowed(subject_hash, job.channel, "marketing", job.tenant_id):
                log.warning(
                    "consent_denied send_job_id=%s channel=%s subject_hash=%s",
                    job.send_job_id, job.channel, subject_hash,
                )
                await consumer.commit()
                continue

            # FIX-08: retry loop with exponential back-off → DLQ on exhaustion
            retry_count = 0
            success = False
            last_exc: Exception | None = None

            while retry_count < MAX_AI_PERSONALISE_RETRIES:
                try:
                    personalised = await llm_personalise(job.template, job.contact)
                    # Produce to engage.send-queue as a full CloudEvent (FIX-01)
                    ce = _build_cloud_event(
                        event_type=CE_TYPE_AI_PERSONALISE_DONE,
                        subject=f"send-job/{job.send_job_id}",
                        tenant_id=job.tenant_id,
                        data={
                            "send_job_id":     job.send_job_id,
                            "subject_id_hash": subject_hash,   # HC-6: no raw email
                            "content":         personalised,
                            "channel":         job.channel,
                            "tenant_id":       job.tenant_id,
                            "personalised_at": datetime.now(UTC).isoformat(),
                        },
                        correlation_id=envelope.correlation_id(),
                        causation_id=envelope.id,
                        actor=envelope.actor(),
                    )
                    await producer.send_and_wait(
                        SEND_QUEUE_TOPIC,
                        value=ce,
                        key=subject_hash.encode(),   # FIX-13: per-recipient ordering
                    )
                    success = True
                    break
                except Exception as exc:
                    retry_count += 1
                    last_exc = exc
                    log.warning(
                        "ai_personalise_attempt_failed send_job_id=%s attempt=%d/%d: %s",
                        job.send_job_id, retry_count, MAX_AI_PERSONALISE_RETRIES, exc,
                    )
                    if retry_count < MAX_AI_PERSONALISE_RETRIES:
                        await asyncio.sleep(2 ** retry_count)

            if success:
                await consumer.commit()
                log.info("ai_personalise_complete send_job_id=%s", job.send_job_id)
            else:
                # FIX-08: route to DLQ after exhausting retries
                dlq_ce = _build_cloud_event(
                    event_type=CE_TYPE_DLQ_AI_PERSONALISE,
                    subject=f"send-job/{job.send_job_id}",
                    tenant_id=job.tenant_id,
                    data={
                        "job_id":         job.send_job_id,
                        "send_job_id":    job.send_job_id,
                        "channel":        job.channel,
                        "tenant_id":      job.tenant_id,
                        "failure_reason": str(last_exc),
                        "failed_at":      datetime.now(UTC).isoformat(),
                        "original_topic": AI_PERSONALISE_TOPIC,
                        "retry_count":    retry_count,
                    },
                    correlation_id=envelope.correlation_id(),
                    causation_id=envelope.id,
                    actor=envelope.actor(),
                )
                await producer.send_and_wait(AI_PERSONALISE_DLQ_TOPIC, value=dlq_ce)
                await consumer.commit()   # commit after DLQ routing to avoid redelivery loop
                log.error(
                    "ai_personalise_dlq send_job_id=%s after %d attempts",
                    job.send_job_id, MAX_AI_PERSONALISE_RETRIES,
                )
    finally:
        await consumer.stop()
        await producer.stop()


# ── Send Queue Consumer (FIX-04) ──────────────────────────────
# Consumes engage.send-queue (previously orphaned) and dispatches
# personalised messages via Brevo. Manual commit, no DLQ (routed
# back to ai-personalise.dlq via the producer that created the message).

async def run_send_queue_consumer(pool: asyncpg.Pool):
    log = logging.getLogger("send-queue")
    consumer = AIOKafkaConsumer(
        SEND_QUEUE_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-send-queue",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log.info("Send-queue consumer started (aiokafka, manual commit)")
    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_AI_PERSONALISE_DONE, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                payload = SendQueueData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_send_queue_data error=%s", exc)
                await consumer.commit()
                continue

            log.info(
                "send_queue_dispatch send_job_id=%s channel=%s tenant_id=%s",
                payload.send_job_id, payload.channel, payload.tenant_id,
            )

            # Consent gate — re-check at dispatch time (defence in depth)
            if not await _consent_allowed(
                payload.subject_id_hash, payload.channel, "marketing", payload.tenant_id
            ):
                log.warning(
                    "send_queue_consent_denied send_job_id=%s channel=%s",
                    payload.send_job_id, payload.channel,
                )
                await consumer.commit()
                continue

            try:
                if payload.channel == "email":
                    # Fetch resolved email from DB using subject_id_hash (HC-6 safe)
                    async with pool.acquire() as conn:
                        await conn.execute("SET LOCAL app.tenant_id = $1", payload.tenant_id)
                        row = await conn.fetchrow(
                            "SELECT email FROM contacts WHERE subject_id_hash = $1 AND tenant_id = $2",
                            payload.subject_id_hash, payload.tenant_id,
                        )
                    if row is None:
                        log.warning("send_queue_no_contact hash=%s", payload.subject_id_hash)
                        await consumer.commit()
                        continue
                    async with httpx.AsyncClient(timeout=10) as http:
                        brevo_resp = await http.post(
                            "https://api.brevo.com/v3/smtp/email",
                            headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
                            json={
                                "sender":      {"name": "i3-Engage", "email": "no-reply@i3technologies.co.ke"},
                                "to":          [{"email": row["email"]}],
                                "subject":     "Your personalised message",
                                "htmlContent": payload.content,
                            },
                        )
                        brevo_resp.raise_for_status()
                await consumer.commit()
                log.info("send_queue_dispatched send_job_id=%s", payload.send_job_id)
            except Exception as exc:
                log.error(
                    "send_queue_dispatch_failed send_job_id=%s: %s — not committing",
                    payload.send_job_id, exc,
                )
    finally:
        await consumer.stop()


# ── Campaign Trigger Consumer (STEP-P3-02) ────────────────────
# Manual offset commit. DLQ after MAX_CAMPAIGN_RETRIES failures.
# FIX-01/FIX-11: reads CloudEvent envelope; produces DLQ as CloudEvent.

MAX_CAMPAIGN_RETRIES   = 3
CAMPAIGN_TRIGGER_TOPIC = "engage.campaign-trigger"
CAMPAIGN_DLQ_TOPIC     = "engage.ai-personalize.dlq"


# ── Structured audit helper (FLAG-5 / EC-3) ───────────────────
def _emit_campaign_audit(
    job_id: str,
    campaign_id: int,
    tenant_id: str,
    outcome: str,
    send_job_id: str,
    correlation_id: str | None = None,
    actor: str | None = None,
    failure_reason: str | None = None,
) -> None:
    payload = {
        "tenant_id":       tenant_id,
        "agent_id":        AGENT_ID,
        "session_id":      job_id,
        "autonomy_tier":   "L0",
        "action":          "campaign_email_dispatch",
        "campaign_id":     campaign_id,
        "send_job_id":     send_job_id,
        "outcome":         outcome,
        "policy_decision": "executed",
        "correlation_id":  correlation_id,
        "actor":           actor,
    }
    if failure_reason:
        payload["failure_reason"] = failure_reason
    try:
        with httpx.Client(timeout=3.0) as client:
            client.post(f"{AGENT_REGISTRY_URL}/decisions", json=payload)
    except Exception as exc:
        logging.getLogger("campaign-trigger").debug(
            "audit_emit_failed job_id=%s: %s", job_id, exc
        )


async def _execute_campaign_send(job: CampaignTriggerData, pool: asyncpg.Pool) -> None:
    """Fetch campaign + contacts and dispatch via Brevo, updating job row throughout.

    HC-4 (FINDING-EC-2): SET LOCAL app.tenant_id is applied BEFORE every SELECT
    and every UPDATE so that RLS policies are enforced on all queries.
    HC-6: subject_id_hash used for consent check; raw email used only for Brevo dispatch.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.tenant_id = $1", job.tenant_id)
            await conn.execute(
                """UPDATE campaign_send_jobs
                   SET status = 'processing', started_at = NOW()
                   WHERE id = $1""",
                job.job_id,
            )
            row = await conn.fetchrow(
                "SELECT * FROM email_campaigns WHERE id = $1", job.campaign_id
            )
            if row is None:
                raise ValueError(f"Campaign {job.campaign_id} not found")

            contacts = await conn.fetch(
                """SELECT id, email, subject_id_hash, first_name, last_name, company
                   FROM contacts
                   WHERE subscribed = true AND $1 = ANY(list_ids)""",
                row["list_id"],
            )

    sent = 0
    failed = 0

    async with httpx.AsyncClient(timeout=10) as http:
        for contact in contacts:
            # HC-6: prefer subject_id_hash for consent check; never fall back to raw email
            subject_hash: str | None = contact["subject_id_hash"]
            if not subject_hash:
                logging.getLogger("campaign-trigger").warning(
                    "missing_subject_id_hash contact_id=%s — skipping (HC-6)", contact["id"]
                )
                failed += 1
                continue

            # Consent gate
            try:
                resp = await http.get(
                    f"{CONSENT_SERVICE_URL}/consent/{subject_hash}",
                    params={
                        "channel":   "email",
                        "purpose":   "marketing",
                        "tenant_id": job.tenant_id,
                    },
                )
                allowed = resp.status_code == 200 and resp.json().get("allowed", False)
            except Exception:
                allowed = False

            if not allowed:
                failed += 1
                continue

            try:
                personalised = await llm_personalise(
                    row["html_template"],
                    {
                        "first_name": contact["first_name"],
                        "last_name":  contact["last_name"],
                        "company":    contact["company"],
                        # NOTE: do not pass raw email into LLM prompt — use display name only
                    },
                )
            except Exception:
                personalised = row["html_template"]

            try:
                brevo_resp = await http.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
                    json={
                        "sender":      {"name": row["from_name"], "email": row["from_email"]},
                        "to":          [{"email": contact["email"]}],
                        "subject":     row["subject"],
                        "htmlContent": personalised,
                    },
                )
                brevo_resp.raise_for_status()
                sent += 1
            except Exception as exc:
                logging.getLogger("campaign-trigger").warning(
                    "brevo_send_failed contact_hash=%s job_id=%s: %s",
                    subject_hash, job.job_id, exc,
                )
                failed += 1

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.tenant_id = $1", job.tenant_id)
            await conn.execute(
                """UPDATE campaign_send_jobs
                   SET status = 'complete', sent = $1, failed = $2, completed_at = NOW()
                   WHERE id = $3""",
                sent, failed, job.job_id,
            )
            await conn.execute(
                "UPDATE email_campaigns SET status = 'sent', sent_at = NOW() WHERE id = $1",
                job.campaign_id,
            )


async def run_campaign_trigger_consumer(pool: asyncpg.Pool) -> None:
    """Consume engage.campaign-trigger with manual offset commit and DLQ routing."""
    log = logging.getLogger("campaign-trigger")
    consumer = AIOKafkaConsumer(
        CAMPAIGN_TRIGGER_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-campaign-trigger",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    dlq_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await consumer.start()
    await dlq_producer.start()
    log.info("Campaign trigger consumer started (aiokafka, manual commit, DLQ=%s)", CAMPAIGN_DLQ_TOPIC)

    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_CAMPAIGN_TRIGGERED, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                trigger = CampaignTriggerData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error("invalid_campaign_trigger offset=%d: %s", msg.offset, exc)
                await consumer.commit()
                continue

            retry_count = trigger.retry_count
            success = False
            last_exc: Exception | None = None

            while retry_count < MAX_CAMPAIGN_RETRIES:
                try:
                    await _execute_campaign_send(trigger, pool)
                    success = True
                    break
                except Exception as exc:
                    retry_count += 1
                    last_exc = exc
                    log.warning(
                        "campaign_send_attempt_failed job_id=%s attempt=%d/%d: %s",
                        trigger.job_id, retry_count, MAX_CAMPAIGN_RETRIES, exc,
                    )
                    if retry_count < MAX_CAMPAIGN_RETRIES:
                        await asyncio.sleep(2 ** retry_count)

            if success:
                await consumer.commit()
                log.info("campaign_send_complete job_id=%s", trigger.job_id)
                _emit_campaign_audit(
                    job_id=trigger.job_id,
                    campaign_id=trigger.campaign_id,
                    tenant_id=trigger.tenant_id,
                    outcome="success",
                    send_job_id=trigger.send_job_id,
                    correlation_id=envelope.correlation_id(),
                    actor=envelope.actor(),
                )
            else:
                dlq_ce = _build_cloud_event(
                    event_type=CE_TYPE_DLQ_CAMPAIGN,
                    subject=f"campaign/{trigger.campaign_id}",
                    tenant_id=trigger.tenant_id,
                    data={
                        **trigger.model_dump(),
                        "failure_reason": str(last_exc),
                        "failed_at":      datetime.now(UTC).isoformat(),
                        "original_topic": CAMPAIGN_TRIGGER_TOPIC,
                        "retry_count":    retry_count,
                    },
                    correlation_id=envelope.correlation_id(),
                    causation_id=envelope.id,
                    actor=envelope.actor(),
                )
                await dlq_producer.send_and_wait(CAMPAIGN_DLQ_TOPIC, value=dlq_ce)
                try:
                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            await conn.execute("SET LOCAL app.tenant_id = $1", trigger.tenant_id)
                            await conn.execute(
                                """UPDATE campaign_send_jobs
                                   SET status = 'failed', completed_at = NOW()
                                   WHERE id = $1""",
                                trigger.job_id,
                            )
                except Exception as db_exc:
                    log.error("failed_to_update_job_status job_id=%s: %s", trigger.job_id, db_exc)
                await consumer.commit()
                log.error(
                    "campaign_send_dlq job_id=%s after %d attempts, routed to %s",
                    trigger.job_id, MAX_CAMPAIGN_RETRIES, CAMPAIGN_DLQ_TOPIC,
                )
                _emit_campaign_audit(
                    job_id=trigger.job_id,
                    campaign_id=trigger.campaign_id,
                    tenant_id=trigger.tenant_id,
                    outcome="failed",
                    send_job_id=trigger.send_job_id,
                    correlation_id=envelope.correlation_id(),
                    actor=envelope.actor(),
                    failure_reason=str(last_exc),
                )
    finally:
        await consumer.stop()
        await dlq_producer.stop()


# ── AI Personalise DLQ Consumer ───────────────────────────────
# Reads from engage.ai-personalize.dlq, persists each message to the
# ai_personalise_dlq table. Manual commit. Drain-and-audit only — no retry.

async def run_ai_personalise_dlq_consumer(pool: asyncpg.Pool) -> None:
    """Consume engage.ai-personalize.dlq and persist to ai_personalise_dlq table."""
    log = logging.getLogger("ai-personalise-dlq")
    consumer = AIOKafkaConsumer(
        AI_PERSONALISE_DLQ_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-ai-personalise-dlq",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log.info("AI personalise DLQ consumer started (topic=%s)", AI_PERSONALISE_DLQ_TOPIC)

    dlq_received_total = 0

    try:
        async for msg in consumer:
            envelope = _parse_cloud_event(msg.value, CE_TYPE_DLQ_AI_PERSONALISE, log)
            if envelope is None:
                await consumer.commit()
                continue

            try:
                dlq_msg = AiPersonaliseDLQData.model_validate(envelope.data)
            except ValidationError as exc:
                log.error(
                    "dlq_invalid_message offset=%d: %s — committing to avoid loop",
                    msg.offset, exc,
                )
                await consumer.commit()
                continue

            log.warning(
                "dlq_message_received job_id=%s send_job_id=%s tenant_id=%s channel=%s "
                "failure_reason=%r retry_count=%d correlation_id=%s",
                dlq_msg.job_id,
                dlq_msg.send_job_id,
                dlq_msg.tenant_id,
                dlq_msg.channel,
                dlq_msg.failure_reason,
                dlq_msg.retry_count,
                envelope.correlation_id(),
            )

            try:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute("SET LOCAL app.tenant_id = $1", dlq_msg.tenant_id)
                        await conn.execute(
                            """INSERT INTO ai_personalise_dlq
                                   (tenant_id, job_id, send_job_id, campaign_id, channel,
                                    failure_reason, original_topic, payload, retry_count,
                                    failed_at, correlation_id)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                               ON CONFLICT DO NOTHING""",
                            dlq_msg.tenant_id,
                            dlq_msg.job_id,
                            dlq_msg.send_job_id,
                            dlq_msg.campaign_id,
                            dlq_msg.channel,
                            dlq_msg.failure_reason,
                            dlq_msg.original_topic,
                            json.dumps(dlq_msg.payload),
                            dlq_msg.retry_count,
                            dlq_msg.failed_at,
                            envelope.correlation_id(),
                        )
            except Exception as db_exc:
                log.error(
                    "dlq_db_write_failed job_id=%s: %s — not committing",
                    dlq_msg.job_id, db_exc,
                )
                continue

            await consumer.commit()
            dlq_received_total += 1
            log.info(
                "dlq_persisted job_id=%s tenant_id=%s channel=%s "
                "engage_ai_personalise_dlq_total=%d",
                dlq_msg.job_id, dlq_msg.tenant_id, dlq_msg.channel, dlq_received_total,
            )
    finally:
        await consumer.stop()


# ── Async main (pool lifecycle owner) ─────────────────────────
async def _async_main(enabled: set):
    log = logging.getLogger("main")
    pool = await get_pool()
    log.info("asyncpg pool ready (min=2 max=10)")

    tasks = []
    if "email" in enabled:
        tasks.append(asyncio.create_task(run_email_event_consumer(pool), name="email-consumer"))
    if "sms" in enabled:
        tasks.append(asyncio.create_task(run_sms_event_consumer(pool), name="sms-consumer"))
    if "ai" in enabled:
        tasks.append(asyncio.create_task(run_ai_personalise_consumer(pool), name="ai-consumer"))
    if "send-queue" in enabled:
        tasks.append(asyncio.create_task(run_send_queue_consumer(pool), name="send-queue-consumer"))
    if "campaign" in enabled:
        tasks.append(asyncio.create_task(run_campaign_trigger_consumer(pool), name="campaign-consumer"))
    if "dlq" in enabled:
        tasks.append(asyncio.create_task(run_ai_personalise_dlq_consumer(pool), name="dlq-consumer"))

    log.info("Running consumers (native async aiokafka): %s", enabled)
    try:
        await asyncio.gather(*tasks)
    finally:
        await pool.close()
        log.info("asyncpg pool closed")


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    log = logging.getLogger("main")
    log.info("Starting i3-Engage Kafka consumers")

    consumers_env = os.getenv("CONSUMERS", "email,sms,ai,send-queue,campaign,dlq")
    enabled = {c.strip() for c in consumers_env.split(",")}

    _stop_event = asyncio.Event()

    def handle_sigterm(*_):
        log.info("SIGTERM received — shutting down")
        _stop_event.set()

    signal.signal(signal.SIGTERM, handle_sigterm)

    asyncio.run(_async_main(enabled))
    log.info("All consumers stopped")
