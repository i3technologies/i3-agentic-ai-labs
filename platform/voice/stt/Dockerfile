FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.111.0 \
    uvicorn[standard]==0.29.0 \
    faster-whisper==1.0.1 \
    python-multipart

COPY stt_service.py .

ENV MODELS_DIR=/models
ENV WHISPER_MODEL=large-v3
ENV COMPUTE_TYPE=int8
ENV BEAM_SIZE=5
ENV VAD_FILTER=true

EXPOSE 8001
CMD ["uvicorn", "stt_service:app", "--host", "0.0.0.0", "--port", "8001"]
