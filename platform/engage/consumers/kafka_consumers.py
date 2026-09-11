"""
i3-Engage Kafka Consumer Service.

Consumers:
  1. EmailEventConsumer   — engage.email-events     → update delivery/open/click status
  2. SMSEventConsumer     — engage.sms-events       → update SMS delivery status
  3. AIPersonalizeConsumer— engage.ai-personalize   → generate personalised content via LiteLLM
  4. CampaignTrigger      — engage.campaign-trigger → schedule bulk sends via Brevo/Mailgun

Env vars:
  KAFKA_BOOTSTRAP     — kafka-bootstrap.i3-messaging.svc.cluster.local:9092
  LITELLM_URL         — LiteLLM gateway
  LITELLM_KEY         — master key
  DATABASE_URL        — engage_db PostgreSQL connection
  BREVO_API_KEY       — Brevo (Sendinblue) API key for email
  MAILGUN_API_KEY     — Mailgun API key (fallback)
  MAILGUN_DOMAIN      — Mailgun domain
"""

import os
import json
import logging
import asyncio
import signal
from datetime import datetime, UTC

import asyncpg
import httpx
from kafka import KafkaConsumer, KafkaProducer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka-bootstrap.i3-messaging.svc.cluster.local:9092")
LITELLM_URL     = os.getenv("LITELLM_URL",     "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY     = os.getenv("LITELLM_KEY",     "")
DATABASE_URL    = os.getenv("DATABASE_URL",     "")
BREVO_KEY       = os.getenv("BREVO_API_KEY",    "")
MAILGUN_KEY     = os.getenv("MAILGUN_API_KEY",  "")
MAILGUN_DOMAIN  = os.getenv("MAILGUN_DOMAIN",   "")

MODEL_FAST      = os.getenv("LITELLM_MODEL_FAST", "qwen-fast")

# ── LiteLLM helper ─────────────────────────────────────────────
async def llm_personalise(template: str, contact: dict) -> str:
    """Personalise a message template for a specific contact."""
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


# ── DB helpers ─────────────────────────────────────────────────
async def get_db() -> asyncpg.Connection:
    return await asyncpg.connect(DATABASE_URL)


async def update_contact_event(conn, contact_id: str, event_type: str, metadata: dict):
    await conn.execute(
        """INSERT INTO contact_events (contact_id, event_type, metadata, created_at)
           VALUES ($1, $2, $3, NOW())
           ON CONFLICT DO NOTHING""",
        contact_id, event_type, json.dumps(metadata),
    )


# ── Email Event Consumer ───────────────────────────────────────
def run_email_event_consumer():
    log = logging.getLogger("email-events")
    consumer = KafkaConsumer(
        "engage.email-events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-email-events",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    log.info("Email event consumer started")
    for msg in consumer:
        event = msg.value
        log.info("Email event: %s", event.get("event"))
        try:
            loop = asyncio.new_event_loop()
            conn = loop.run_until_complete(get_db())
            loop.run_until_complete(update_contact_event(
                conn,
                contact_id=event.get("email", ""),
                event_type=event.get("event", "unknown"),
                metadata={
                    "message_id": event.get("message_id"),
                    "timestamp":  event.get("timestamp"),
                },
            ))
            loop.run_until_complete(conn.close())
        except Exception as exc:
            log.error("Failed to process email event: %s", exc)


# ── SMS Event Consumer ────────────────────────────────────────
def run_sms_event_consumer():
    log = logging.getLogger("sms-events")
    consumer = KafkaConsumer(
        "engage.sms-events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-sms-events",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    log.info("SMS event consumer started")
    for msg in consumer:
        event = msg.value
        log.info("SMS event: status=%s", event.get("status"))
        try:
            loop = asyncio.new_event_loop()
            conn = loop.run_until_complete(get_db())
            loop.run_until_complete(conn.execute(
                """UPDATE sms_messages SET status = $1, updated_at = NOW()
                   WHERE provider_message_id = $2""",
                event.get("status", "unknown"),
                event.get("message_id"),
            ))
            loop.run_until_complete(conn.close())
        except Exception as exc:
            log.error("Failed to process SMS event: %s", exc)


# ── AI Personalise Consumer ────────────────────────────────────
def run_ai_personalise_consumer():
    log = logging.getLogger("ai-personalise")
    consumer = KafkaConsumer(
        "engage.ai-personalize",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="engage-ai-personalise",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    log.info("AI personalise consumer started")
    for msg in consumer:
        job = msg.value
        template    = job.get("template", "")
        contact     = job.get("contact", {})
        send_job_id = job.get("send_job_id")
        log.info("Personalising for contact: %s", contact.get("email"))
        try:
            loop = asyncio.new_event_loop()
            personalised = loop.run_until_complete(llm_personalise(template, contact))
            # Publish personalised message back to send queue
            producer.send("engage.send-queue", {
                "send_job_id": send_job_id,
                "contact":     contact,
                "content":     personalised,
                "channel":     job.get("channel", "email"),
                "personalised_at": datetime.now(UTC).isoformat(),
            })
        except Exception as exc:
            log.error("AI personalisation failed: %s", exc)


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import threading

    log = logging.getLogger("main")
    log.info("Starting i3-Engage Kafka consumers")

    # Graceful shutdown
    stop_event = threading.Event()
    def handle_sigterm(*_):
        log.info("SIGTERM received — shutting down")
        stop_event.set()
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Which consumers to run (controlled by CONSUMERS env var, comma-separated)
    consumers_env = os.getenv("CONSUMERS", "email,sms,ai")
    enabled = {c.strip() for c in consumers_env.split(",")}

    threads = []
    if "email" in enabled:
        t = threading.Thread(target=run_email_event_consumer, daemon=True, name="email-consumer")
        t.start(); threads.append(t)
    if "sms" in enabled:
        t = threading.Thread(target=run_sms_event_consumer, daemon=True, name="sms-consumer")
        t.start(); threads.append(t)
    if "ai" in enabled:
        t = threading.Thread(target=run_ai_personalise_consumer, daemon=True, name="ai-consumer")
        t.start(); threads.append(t)

    log.info("Running consumers: %s", enabled)
    stop_event.wait()
    log.info("All consumers stopped")
