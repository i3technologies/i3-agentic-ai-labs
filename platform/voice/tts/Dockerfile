FROM python:3.11-slim

# System deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.111.0 \
    uvicorn[standard]==0.29.0 \
    TTS==0.22.0 \
    torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu \
    numpy \
    soundfile \
    python-multipart

COPY tts_service.py .

ENV MODELS_DIR=/models
ENV CLONES_DIR=/clones
ENV DEFAULT_LANGUAGE=en

EXPOSE 8000
CMD ["uvicorn", "tts_service:app", "--host", "0.0.0.0", "--port", "8000"]
