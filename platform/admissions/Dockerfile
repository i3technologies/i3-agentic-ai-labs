FROM python:3.12-slim AS base

# Use nobody (65534) — universally non-root, satisfies OpenShift runAsNonRoot: true
RUN useradd --system --uid 65534 --no-create-home nobody-app 2>/dev/null || true

WORKDIR /app

# System deps — only what uvicorn + grpc need.
# `apt-get upgrade` resolves OS-level CVEs: CVE-2026-103111 (libpcre2),
# CVE-2026-75804/84782 (openssl) flagged by Trivy P2-GATE-10.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

# ── Dependencies layer ───────────────────────────────────────
FROM base AS deps
COPY requirements.txt .
# Pin setuptools<80: setuptools>=80 removed pkg_resources which
# opentelemetry-instrumentation-fastapi==0.46b0 still imports.
RUN pip install --no-cache-dir --upgrade pip "setuptools<80" \
 && pip install --no-cache-dir -r requirements.txt

# ── App layer ────────────────────────────────────────────────
FROM deps AS app
COPY admissions_agent.py .

# NOTE: download_model.py (BGE-Large pre-fetch) was removed.
# sentence-transformers is no longer a dependency — all embedding/RAG
# calls route through the MCP Gateway (chroma.search tool, STEP-P2-04).

RUN chown -R 65534:65534 /app
USER 65534

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "admissions_agent:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]
