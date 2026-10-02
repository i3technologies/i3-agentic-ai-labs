FROM python:3.11-slim AS base

# Install system deps: ffmpeg + ffprobe
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download faster-whisper model at build time
ARG WHISPER_MODEL=small
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')"

COPY pipeline.py ./

# Run as non-root
RUN useradd --system --uid 1000 pipeline
USER pipeline

EXPOSE 8090
ENV PORT=8090
CMD ["uvicorn", "pipeline:app", "--host", "0.0.0.0", "--port", "8090", "--log-level", "info"]
