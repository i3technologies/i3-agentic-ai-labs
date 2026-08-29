FROM python:3.12-slim

RUN useradd --system --uid 0 --no-create-home root 2>/dev/null || true

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    libseccomp-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Firecracker binary
RUN arch=$(uname -m) \
 && curl -fsSL "https://github.com/firecracker-microvm/firecracker/releases/download/v1.7.0/firecracker-v1.7.0-${arch}.tgz" \
    | tar xz --strip-components=1 -C /usr/bin/ "release-v1.7.0-${arch}/firecracker-v1.7.0-${arch}" \
 && mv "/usr/bin/firecracker-v1.7.0-${arch}" /usr/bin/firecracker \
 && chmod +x /usr/bin/firecracker

COPY platform/evalos/sandbox/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY platform/evalos/sandbox_daemon.py .
COPY platform/evalos/sandbox/daemon.py sandbox/

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "sandbox_daemon:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
