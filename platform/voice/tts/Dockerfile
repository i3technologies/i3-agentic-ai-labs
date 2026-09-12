FROM image-registry.openshift-image-registry.svc:5000/openshift/python:3.11-slim

# System deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install torch CPU-only first, then the rest from PyPI
RUN pip install --no-cache-dir \
    torch==2.2.2 \
    torchaudio==2.2.2 \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 \
    TTS==0.22.0 \
    numpy \
    soundfile \
    python-multipart

COPY tts_service.py .

ENV MODELS_DIR=/models
ENV CLONES_DIR=/clones
ENV DEFAULT_LANGUAGE=en

EXPOSE 8000
CMD ["uvicorn", "tts_service:app", "--host", "0.0.0.0", "--port", "8000"]
