FROM python:3.12-slim AS base

# Security hardening
RUN useradd --system --uid 1000 --no-create-home appuser

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

# ── Dependencies layer ───────────────────────────────────────
FROM base AS deps
COPY platform/admissions/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── App layer ────────────────────────────────────────────────
FROM deps AS app
COPY platform/admissions/admissions_agent.py .

# BGE-Large pre-download (done at build time, not runtime)
COPY platform/admissions/fastapi/download_model.py .
RUN python download_model.py || true   # Non-fatal: model also downloaded at first request

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "admissions_agent:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]
