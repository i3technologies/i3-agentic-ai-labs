"""
tts_service.py  —  i3 Voice TTS Service v3
===========================================
FastAPI TTS backed by pyttsx3 / espeak-ng.
Zero ML dependencies — no torch, no librosa, no numba.

Endpoints:
  GET  /v1/health     Health check
  POST /v1/tts        Synthesise speech → WAV audio stream
  GET  /v1/voices     List available voice IDs

Authentication: Bearer token via VOICE_API_KEY env var.
"""

import os
import io
import logging
import subprocess
import tempfile
from typing import Annotated, Literal, Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError, field_validator

log = logging.getLogger("tts-service")
logging.basicConfig(level=logging.INFO)

API_KEY      = os.getenv("VOICE_API_KEY", "")
DEFAULT_LANG = os.getenv("DEFAULT_LANGUAGE", "en")
VOICE_RATE   = int(os.getenv("VOICE_RATE", "150"))

# Supported espeak-ng language codes
_SUPPORTED_LANGS = frozenset({
    "en", "en-us", "en-gb", "sw", "fr", "de", "es", "pt", "ar", "hi",
})

app = FastAPI(title="i3 Voice TTS Service", version="3.0.0")
# CORS is enforced at the Kong API Gateway layer (STEP-P2-07).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.i3technologies.co.ke", "https://evalos.i3technologies.co.ke"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    allow_credentials=True,
)


# ── Structured validation-error handler (IMP-05) ──────────────────────────────
# Log every Pydantic ValidationError with structured fields before returning 422.
@app.exception_handler(ValidationError)
async def _validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    log.error(
        "tts_validation_error path=%s errors=%s",
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


def check_auth(authorization: Optional[str] = Header(default=None)):
    if not API_KEY:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    if authorization.removeprefix("Bearer ").strip() != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


class TTSRequest(BaseModel):
    """Validated TTS synthesis request (IMP-05: Pydantic constraints enforced before handler)."""

    text: Annotated[str, Field(min_length=1, max_length=5000,
                               description="Text to synthesise (1–5000 chars)")]
    language: Annotated[str, Field(default="en",
                                   description="BCP-47 language code")] = "en"
    speed: Annotated[float, Field(default=1.0, ge=0.5, le=2.0,
                                  description="Speech rate multiplier (0.5–2.0)")] = 1.0

    @field_validator("language")
    @classmethod
    def _validate_language(cls, v: str) -> str:
        normalised = v.lower().strip()
        if normalised not in _SUPPORTED_LANGS:
            raise ValueError(
                f"Unsupported language '{v}'. Supported: {sorted(_SUPPORTED_LANGS)}"
            )
        return normalised


@app.get("/v1/health")
def health():
    # Quick espeak sanity check
    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True, timeout=3)
        engine = "espeak-ng"
    except Exception:
        engine = "unavailable"
    return {"status": "ok", "service": "voice-tts", "engine": engine, "version": "3.0.0"}


@app.post("/v1/tts", dependencies=[Depends(check_auth)])
async def synthesise(req: TTSRequest):
    """Synthesise speech via espeak-ng. Returns WAV audio.

    Input is fully validated by TTSRequest before this handler runs (IMP-05).
    ValidationError is logged and returned as 422 by the exception handler above.
    """
    # req.text is guaranteed non-empty and ≤ 5 000 chars by the Pydantic model.
    text = req.text.strip()
    if not text:
        # Edge case: text was all whitespace — not reachable via normal validation
        # but guard defensively.
        raise HTTPException(status_code=400, detail="text is required")

    # Map speed (0.5–2.0) to espeak words-per-minute (80–400)
    wpm = max(80, min(400, int(VOICE_RATE * req.speed)))

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            ["espeak-ng", "-w", tmp_path, "-s", str(wpm), text],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"espeak-ng error: {result.stderr.decode()}")

        with open(tmp_path, "rb") as f:
            audio = f.read()
        os.unlink(tmp_path)

        log.info("TTS synthesised %d chars → %d bytes WAV", len(text), len(audio))
        return StreamingResponse(io.BytesIO(audio), media_type="audio/wav",
                                  headers={"Content-Length": str(len(audio))})
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="TTS synthesis timed out")
    except Exception as e:
        log.error("TTS error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/voices", dependencies=[Depends(check_auth)])
def list_voices():
    """List available espeak-ng voices."""
    try:
        result = subprocess.run(["espeak-ng", "--voices=en"], capture_output=True, timeout=5, text=True)
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and not l.startswith("Pty")]
        voices = [l.split()[3] for l in lines if len(l.split()) >= 4][:10]
    except Exception:
        voices = ["en", "en-us", "en-gb"]
    return {"voices": voices, "engine": "espeak-ng"}
