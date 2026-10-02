"""
CRM Intelligence — Celery Application & Queue Architecture
File:      platform/crm/celery_app.py
Namespace: crm-intelligence

Queue topology (6 dedicated queues, each with a separate worker pool):

  import      ← CSV/CRM ingestion; idempotent upserts to organisations + contacts
  discovery   ← TAM scoring, org-level signal enrichment
  crawl       ← HC-5 gated HTTP/DNS crawling (robots.txt + OPA policy checked first)
  extract     ← NLP extraction of contact fields from crawled HTML/text
  verify      ← DNS MX + syntax verification of email addresses
  export      ← Suppression-checked, HMAC-validated contact export to downstream CRMs

HC-4: every task receives tenant_id as a mandatory kwarg.
HC-5: crawl tasks call evaluate_source() before any external I/O.
HC-6: all PII hashing uses hmac_sha256_hex() from crawler.py.
Rule 1: propensity_score is never overwritten by any enrichment task.
Rule 2: no synthetic email generation — observed source_url required.
Rule 3: crawl tasks enforce rate limits via Redis token-bucket (rate_limiter.py).
Rule 4: export tasks run suppression check before emitting any contact.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import worker_process_init
from kombu import Exchange, Queue

# ── Broker / result backend ────────────────────────────────────────────────
# Both URLs are injected via ExternalSecrets from OpenBao i3/crm/redis.
REDIS_URL = os.environ.get("CELERY_BROKER_URL", "redis://:changeme@crm-redis:6379/0")
RESULT_BACKEND_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://:changeme@crm-redis:6379/1")

app = Celery("crm_intelligence", broker=REDIS_URL, backend=RESULT_BACKEND_URL)

# ── Exchange ───────────────────────────────────────────────────────────────
crm_exchange = Exchange("crm", type="direct")

# ── Queue definitions ──────────────────────────────────────────────────────
QUEUES = (
    # Priority HIGH — data ingestion gate; blocks all downstream work
    Queue("import",    crm_exchange, routing_key="import",    max_priority=10),
    # Priority MEDIUM — org-level intelligence, fan-out to crawl
    Queue("discovery", crm_exchange, routing_key="discovery", max_priority=7),
    # Priority MEDIUM — external I/O; rate-limited by token bucket (Rule 3)
    Queue("crawl",     crm_exchange, routing_key="crawl",     max_priority=5),
    # Priority MEDIUM — CPU-bound NLP; no network I/O
    Queue("extract",   crm_exchange, routing_key="extract",   max_priority=5),
    # Priority LOW — async DNS MX checks; can be deferred
    Queue("verify",    crm_exchange, routing_key="verify",    max_priority=3),
    # Priority LOW — final suppression sweep + downstream push
    Queue("export",    crm_exchange, routing_key="export",    max_priority=3),
)

# ── Celery configuration ───────────────────────────────────────────────────
app.config_from_object({
    # Broker
    "broker_url": REDIS_URL,
    "broker_transport_options": {
        "visibility_timeout": 3600,       # 1 hour — long crawl tolerance
        "queue_order_strategy": "priority",
    },

    # Result backend
    "result_backend": RESULT_BACKEND_URL,
    "result_expires": 86400,              # 24 h TTL on task results

    # Queues & routing
    "task_queues": QUEUES,
    "task_default_queue": "import",
    "task_default_exchange": "crm",
    "task_default_routing_key": "import",
    "task_routes": {
        "crm.tasks.import.*":    {"queue": "import"},
        "crm.tasks.discovery.*": {"queue": "discovery"},
        "crm.tasks.crawl.*":     {"queue": "crawl"},
        "crm.tasks.extract.*":   {"queue": "extract"},
        "crm.tasks.verify.*":    {"queue": "verify"},
        "crm.tasks.export.*":    {"queue": "export"},
    },

    # Worker reliability
    "task_acks_late": True,               # ack only after successful execution
    "task_reject_on_worker_lost": True,   # requeue if worker crashes mid-task
    "worker_prefetch_multiplier": 1,      # one task at a time per worker slot
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],

    # Retry policy defaults (tasks override per-task)
    "task_annotations": {
        "crm.tasks.crawl.*": {
            "rate_limit": "30/m",         # coarse Celery limit; fine-grained by token bucket
            "max_retries": 5,
            "default_retry_delay": 60,
        },
        "crm.tasks.verify.*": {
            "rate_limit": "120/m",
            "max_retries": 3,
            "default_retry_delay": 30,
        },
        "crm.tasks.export.*": {
            "max_retries": 3,
            "default_retry_delay": 120,
        },
    },

    # Beat schedule — periodic maintenance tasks
    "beat_schedule": {
        # Re-queue stale unverified contacts every 6 hours
        "reverify-unverified-contacts": {
            "task": "crm.tasks.verify.reverify_stale_contacts",
            "schedule": 21600,             # 6 h
            "options": {"queue": "verify"},
        },
        # Flush completed export batches every hour
        "flush-export-batches": {
            "task": "crm.tasks.export.flush_export_batches",
            "schedule": 3600,
            "options": {"queue": "export"},
        },
    },
})

# ── Autodiscovery ──────────────────────────────────────────────────────────
app.autodiscover_tasks(["crm.tasks"])


@worker_process_init.connect
def _validate_secrets(**kwargs):
    """
    HC-6: Fail fast if CRM_HMAC_SECRET is missing on worker startup.
    Called once per worker process before any task is accepted.
    """
    from crm.crawler import _get_hmac_secret  # noqa: PLC0415 — intentional deferred import
    _get_hmac_secret()                        # raises RuntimeError if secret unset
