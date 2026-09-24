"""
sit_tutor.py  —  i3 SIT AI Tutor Agent
========================================
Lightweight conversational AI tutor backed by LiteLLM.

Endpoints:
  GET  /health        Health check
  POST /chat          Send a message, get AI response
  POST /chat/reset    Clear session history
"""

import os
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

log = logging.getLogger("sit-tutor")
logging.basicConfig(level=logging.INFO)

LITELLM_URL  = os.environ.get("LITELLM_URL", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY  = os.environ.get("LITELLM_KEY", "")
TUTOR_MODEL  = os.environ.get("TUTOR_MODEL", "granite-nano")  # granite-nano is fastest (2B)

app = FastAPI(title="i3 SIT Tutor Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory session store: {session_id: [{"role":..,"content":..}]}
_sessions: dict = {}

SYSTEM_PROMPT = (
    "You are Zuri, an AI learning tutor for the i3 Smart ICT Training (SIT) platform. "
    "You help Kenyan learners understand digital skills, ICT concepts, and course content. "
    "Be encouraging, concise, and use simple English. If asked in Swahili, respond in Swahili."
)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    model: Optional[str] = None


class ResetRequest(BaseModel):
    session_id: Optional[str] = "default"


@app.get("/health")
def health():
    return {"status": "ok", "service": "sit-tutor-agent", "model": TUTOR_MODEL}


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    session_id = req.session_id or "default"
    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    _sessions[session_id].append({"role": "user", "content": req.message})

    model = req.model or TUTOR_MODEL
    payload = {
        "model": model,
        "messages": _sessions[session_id],
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=115.0, write=10.0, pool=10.0)) as client:
            resp = await client.post(f"{LITELLM_URL}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LiteLLM timeout — model may be loading, try again in 30s")
    except httpx.HTTPStatusError as e:
        log.error("LiteLLM error %s: %s", e.response.status_code, e.response.text)
        raise HTTPException(status_code=502, detail=f"LiteLLM error: {e.response.status_code}")
    except Exception as e:
        log.error("Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    if not data.get("choices"):
        log.error("LiteLLM response has no choices: %s", data)
        raise HTTPException(status_code=502, detail=f"LiteLLM returned no choices: {data.get('error', data)}")

    reply = data["choices"][0]["message"]["content"]
    _sessions[session_id].append({"role": "assistant", "content": reply})

    # Trim session history to last 20 turns to avoid context overflow
    if len(_sessions[session_id]) > 41:  # system + 20 turns × 2
        _sessions[session_id] = [_sessions[session_id][0]] + _sessions[session_id][-40:]

    return {
        "reply": reply,
        "session_id": session_id,
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }


@app.post("/chat/reset")
def reset_session(req: ResetRequest):
    session_id = req.session_id or "default"
    if session_id in _sessions:
        del _sessions[session_id]
    return {"status": "ok", "session_id": session_id, "message": "Session history cleared"}


@app.get("/sessions")
def list_sessions():
    return {"sessions": list(_sessions.keys()), "count": len(_sessions)}
