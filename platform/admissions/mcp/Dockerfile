FROM python:3.12-slim

# Use nobody (65534) — universally non-root, satisfies OpenShift runAsNonRoot: true
# without requiring a namespace-specific UID range.
RUN useradd --system --uid 65534 --no-create-home nobody-app 2>/dev/null || true

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Pin setuptools<80 for pkg_resources compatibility with opentelemetry-instrumentation
RUN pip install --no-cache-dir --upgrade pip "setuptools<80" \
 && pip install --no-cache-dir -r requirements.txt

COPY mcp_connectors.py .

RUN chown -R 65534:65534 /app
USER 65534

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:9000/health || exit 1

CMD ["uvicorn", "mcp_connectors:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1"]
