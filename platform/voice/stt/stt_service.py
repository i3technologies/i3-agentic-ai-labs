"""
stt_service.py
==============
FastAPI wrapper for faster-whisper Speech-to-Text.
Model: large-v3 (multilingual — supports English, Swahili, etc.)
Quantisation: int8 (CPU-optimised, fits in ~2 GB RAM)

Endpoints:
  GET  /v1/health         Health check
  POST /v1/transcribe     Transcribe audio file → transcript + metadata

Authentication: Bearer token via VOICE_API_KEY env var.
"""

import os
import io
import time
import logging
import tempfile
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from pydantic import BaseModel

log = logging.getLogger("stt-service")
logging.basicConfig(level=logging.INFO)

MODELS_DIR   = os.getenv("MODELS_DIR", "/models")
MODEL_SIZE   = os.getenv("WHISPER_MODEL", "large-v3")
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "int8")
BEAM_SIZE    = int(os.getenv("BEAM_SIZE", "5"))
VAD_FILTER   = os.getenv("VAD_FILTER", "true").lower() == "true"
API_KEY      = os.getenv("VOICE_API_KEY", "")

app = FastAPI(title="i3 Voice STT Service", version="1.0.0")

_whisper_model = None


def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        log.info("Loading faster-whisper %s (%s)…", MODEL_SIZE, COMPUTE_TYPE)
        _whisper_model = WhisperModel(
            MODEL_SIZE,
            device="cpu",
            compute_type=COMPUTE_TYPE,
            download_root=MODELS_DIR,
        )
        log.info("Whisper loaded ✓")
    return _whisper_model


def check_auth(authorization: Optional[str] = Header(default=None)):
    if not API_KEY:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    if authorization.removeprefix("Bearer ").strip() != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── Models ────────────────────────────────────────────────────
class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscribeResponse(BaseModel):
    transcript: str
    language: str
    language_probability: float
    duration_s: float
    segments: list[TranscriptSegment]
    processing_ms: int


# ── Routes ───────────────────────────────────────────────────
@app.get("/v1/health")
def health():
    return {"status": "ok", "service": "voice-stt", "model": MODEL_SIZE}


@app.post("/v1/transcribe", response_model=TranscribeResponse, dependencies=[Depends(check_auth)])
async def transcribe(
    audio_file: UploadFile = File(...),
    language: Optional[str] = None,   # hint: "en", "sw", etc. None = auto-detect
):
    """
    Transcribe an uploaded audio file.
    Accepts: WAV, MP3, OGG, WEBM, M4A (anything ffmpeg handles).
    Returns: full transcript + per-segment timestamps + detected language.
    """
    audio_bytes = await audio_file.read()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Audio file too small or empty")

    t_start = time.time()
    model = get_whisper()

    # Write to temp file (faster-whisper needs a file path, not bytes)
    suffix = (audio_file.filename or ".wav").rsplit(".", 1)[-1]
    with tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments_iter, info = model.transcribe(
            tmp_path,
            language=language,
            beam_size=BEAM_SIZE,
            vad_filter=VAD_FILTER,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        segments = list(segments_iter)
        full_transcript = " ".join(s.text.strip() for s in segments)
        processing_ms = int((time.time() - t_start) * 1000)

        log.info(
            "Transcribed %.1fs audio → %d chars in %dms [%s %.0f%%]",
            info.duration,
            len(full_transcript),
            processing_ms,
            info.language,
            info.language_probability * 100,
        )

        return TranscribeResponse(
            transcript=full_transcript,
            language=info.language,
            language_probability=info.language_probability,
            duration_s=info.duration,
            segments=[
                TranscriptSegment(start=s.start, end=s.end, text=s.text.strip())
                for s in segments
            ],
            processing_ms=processing_ms,
        )
    except Exception as e:
        log.error("Transcription error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)
