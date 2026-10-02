# ============================================================
# CRM Intelligence Service — Multi-Stage Dockerfile
# Image:     icr.io/i3-technologies/crm-intel-worker
# Base:      python:3.11-slim (non-root, minimal attack surface)
#
# HC-7: No DEV_BYPASS_AUTH baked in. All secrets injected at runtime
#       via ExternalSecrets Operator (see manifests/external-secrets.yaml).
# HC-6: CRM_HMAC_SECRET must be present at container start; the
#       worker_process_init signal validates this and fails fast.
# Security: runs as UID 1001, read-only root FS, no new privileges.
# ============================================================

# ── Stage 1: build ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install only build-time deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: create a non-root user (UID 1001, matching SCC in security-profiles.yaml)
RUN groupadd --gid 1001 crm && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /sbin/nologin crm

# Install runtime system deps only (libpq for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application source
COPY celery_app.py  ./
COPY crawler.py     ./
COPY rate_limiter.py ./
COPY tasks.py       ./
COPY main.py        ./

# Ensure the crm package is importable as 'crm.*'
RUN echo "" > __init__.py

# HC-7: no secrets baked in — all env vars injected at runtime
# ENV CRM_HMAC_SECRET is intentionally NOT set here

USER crm

# ── Entrypoint selection via CMD override ──────────────────────────────────────
#
# API server:
#   docker run ... uvicorn main:app --host 0.0.0.0 --port 8000
#
# Celery worker (crawl + extract + verify queues):
#   docker run ... celery -A crm.celery_app worker -Q crawl,extract,verify -c 4
#
# Celery beat scheduler:
#   docker run ... celery -A crm.celery_app beat --loglevel=INFO
#
# Default: API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]

EXPOSE 8000

# Healthcheck — maps to /healthz endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
