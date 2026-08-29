FROM python:3.12-slim

RUN useradd --system --uid 1000 --no-create-home appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
 && rm -rf /var/lib/apt/lists/*

COPY platform/admissions/mcp/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY platform/admissions/mcp/mcp_connectors.py .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:9000/health || exit 1

CMD ["uvicorn", "mcp_connectors:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1"]
