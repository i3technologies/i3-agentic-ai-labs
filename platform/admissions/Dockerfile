FROM python:3.12-slim AS base

# Security hardening — non-root user
RUN useradd --system --uid 1000 --no-create-home appuser

WORKDIR /app

# System deps — only what uvicorn + grpc need
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

# ── Dependencies layer ───────────────────────────────────────
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── App layer ────────────────────────────────────────────────
FROM deps AS app
COPY admissions_agent.py .

# NOTE: download_model.py (BGE-Large pre-fetch) was removed.
# sentence-transformers is no longer a dependency — all embedding/RAG
# calls route through the MCP Gateway (chroma.search tool, STEP-P2-04).

# OpenShift assigns a namespace-allocated UID at runtime (runAsNonRoot: true in Deployment).
# Do NOT pin USER appuser (UID 1000) — it conflicts with OpenShift SCC UID ranges.
RUN chown -R appuser:appuser /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "admissions_agent:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]
