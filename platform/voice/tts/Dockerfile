FROM image-registry.openshift-image-registry.svc:5000/openshift/python:3.11-slim

# espeak-ng provides offline TTS — no torch, no librosa, no numba
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-ng-dev \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 \
    python-multipart \
    "pyttsx3==2.98" \
    "soundfile==0.12.1" \
    "numpy<2.0"

COPY tts_service.py .

ENV DEFAULT_LANGUAGE=en
ENV VOICE_RATE=150
ENV VOICE_VOLUME=0.9

EXPOSE 8000
CMD ["uvicorn", "tts_service:app", "--host", "0.0.0.0", "--port", "8000"]
