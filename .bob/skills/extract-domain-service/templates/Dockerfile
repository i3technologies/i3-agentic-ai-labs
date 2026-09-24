# ── Stage 1: Build ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

COPY . .

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user — HC principle: minimal privilege
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local
# Copy application source
COPY --from=builder /build .

# Ensure non-root ownership
RUN chown -R appuser:appgroup /app

USER appuser

# ── Health / readiness port ──────────────────────────────────────────────────
EXPOSE 8000

# ── Entrypoint ───────────────────────────────────────────────────────────────
# DATABASE_URL and other secrets are injected by OpenBao agent sidecar at runtime
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
