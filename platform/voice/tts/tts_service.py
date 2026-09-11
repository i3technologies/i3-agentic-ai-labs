"""
tts_service.py
==============
FastAPI wrapper for Coqui XTTS-v2 Text-to-Speech + Voice Cloning.

Endpoints:
  GET  /v1/health          Health check
  POST /v1/tts             Synthesise speech from text
  POST /v1/clone           Clone a voice from a short WAV sample
  GET  /v1/voices          List available voice IDs

Authentication: Bearer token via VOICE_API_KEY env var.
"""

import os
import io
import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import soundfile as sf
import numpy as np

log = logging.getLogger("tts-service")
logging.basicConfig(level=logging.INFO)

MODELS_DIR  = Path(os.getenv("MODELS_DIR", "/models"))
CLONES_DIR  = Path(os.getenv("CLONES_DIR", "/clones"))
API_KEY     = os.getenv("VOICE_API_KEY", "")
DEFAULT_LANG = os.getenv("DEFAULT_LANGUAGE", "en")

MODELS_DIR.mkdir(parents=True, exist_ok=True)
CLONES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="i3 Voice TTS Service", version="1.0.0")

# Global TTS model (loaded once on startup)
_tts_model = None


def get_tts():
    global _tts_model
    if _tts_model is None:
        from TTS.api import TTS
        log.info("Loading XTTS-v2 model (first request may take 30–60s)…")
        _tts_model = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=False,
        )
        log.info("XTTS-v2 loaded ✓")
    return _tts_model


def check_auth(authorization: Optional[str] = Header(default=None)):
    if not API_KEY:
        return  # auth disabled if key not set
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    if authorization.removeprefix("Bearer ").strip() != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── Models ────────────────────────────────────────────────────
class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None   # voice ID from /v1/clone
    language: str = DEFAULT_LANG
    speed: float = 1.0


class CloneResponse(BaseModel):
    voice_id: str
    message: str


# ── Routes ───────────────────────────────────────────────────
@app.get("/v1/health")
def health():
    return {"status": "ok", "service": "voice-tts", "model": "xtts_v2"}


@app.post("/v1/tts", dependencies=[Depends(check_auth)])
async def synthesise(req: TTSRequest):
    """Synthesise speech. Returns WAV audio as streaming response."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    if len(req.text) > 5000:
        raise HTTPException(status_code=400, detail="text exceeds 5000 char limit")

    tts = get_tts()

    # Resolve speaker WAV if voice_id provided
    speaker_wav = None
    if req.voice_id:
        clone_path = CLONES_DIR / f"{req.voice_id}.wav"
        if not clone_path.exists():
            raise HTTPException(status_code=404, detail=f"voice_id {req.voice_id!r} not found")
        speaker_wav = str(clone_path)

    try:
        # Generate waveform
        wav = tts.tts(
            text=req.text,
            speaker_wav=speaker_wav,
            language=req.language,
            speed=req.speed,
        )
        # Encode to WAV bytes in-memory
        buf = io.BytesIO()
        sf.write(buf, np.array(wav), samplerate=24000, format="WAV")
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/wav")
    except Exception as e:
        log.error("TTS synthesis error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/clone", response_model=CloneResponse, dependencies=[Depends(check_auth)])
async def clone_voice(audio_file: UploadFile = File(...)):
    """
    Clone a voice from a short WAV sample (6–60 seconds).
    Returns a voice_id that can be passed to /v1/tts.
    """
    if not audio_file.content_type or "audio" not in audio_file.content_type:
        raise HTTPException(status_code=400, detail="audio file required (WAV/MP3/OGG)")

    audio_bytes = await audio_file.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Audio file too small — need at least 6 seconds")

    voice_id = str(uuid.uuid4())
    clone_path = CLONES_DIR / f"{voice_id}.wav"

    try:
        # Write uploaded audio to clone store
        # XTTS-v2 accepts WAV directly; convert if needed
        buf = io.BytesIO(audio_bytes)
        audio_data, sample_rate = sf.read(buf)
        # Resample to 22050 Hz if needed (XTTS-v2 requirement)
        if sample_rate != 22050:
            import librosa
            audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=22050)
        sf.write(str(clone_path), audio_data, samplerate=22050, format="WAV")

        log.info("Voice clone created: %s", voice_id)
        return CloneResponse(
            voice_id=voice_id,
            message=f"Voice cloned successfully. Use voice_id={voice_id!r} in /v1/tts requests.",
        )
    except Exception as e:
        log.error("Voice clone error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/voices", dependencies=[Depends(check_auth)])
def list_voices():
    """List all available cloned voice IDs."""
    voices = [p.stem for p in CLONES_DIR.glob("*.wav")]
    return {"voices": voices, "count": len(voices)}
