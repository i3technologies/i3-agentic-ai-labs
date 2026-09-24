"""
Live Streaming Router — manage live sessions, stream keys, VOD pipeline trigger.
"""
import uuid
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import httpx
import os

from app.db import get_db

logger = logging.getLogger("smartlab.live")
router = APIRouter()

N8N_URL     = os.environ.get("N8N_URL", "http://n8n.i3-ott.svc:5678")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
LIVE_RTMP   = os.environ.get("LIVE_RTMP_SERVER", "rtmp://149.81.34.82:1935/live")
HLS_BASE    = os.environ.get("HLS_CDN_BASE", "https://cdn.i3technologies.co.ke/hls")


class CreateSessionRequest(BaseModel):
    title:            str
    course_id:        Optional[str] = None
    author_id:        str = ""
    chat_enabled:     bool = True
    ai_tutor_enabled: bool = True
    scheduled_at:     Optional[str] = None


class EndSessionRequest(BaseModel):
    session_id:        str
    trigger_vod:       bool = True  # auto-create VOD from recording


@router.post("/sessions")
async def create_live_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a live session and generate a secure RTMP stream key."""
    session_id  = str(uuid.uuid4())
    # Cryptographically secure stream key — 24 chars
    stream_key  = f"i3-{secrets.token_urlsafe(18)}"
    rtmp_url    = f"{LIVE_RTMP}/{stream_key}"
    hls_url     = f"{HLS_BASE}/live/{stream_key}_720p/index.m3u8"

    await db.execute(text("""
        INSERT INTO live_sessions
          (id, course_id, author_id, title, stream_key, rtmp_url, hls_url,
           status, chat_enabled, ai_tutor_enabled)
        VALUES
          (:id, :course_id, :author_id, :title, :key, :rtmp, :hls,
           'scheduled', :chat, :tutor)
    """), {
        "id":         session_id,
        "course_id":  req.course_id,
        "author_id":  req.author_id or "00000000-0000-0000-0000-000000000000",
        "title":      req.title,
        "key":        stream_key,
        "rtmp":       rtmp_url,
        "hls":        hls_url,
        "chat":       req.chat_enabled,
        "tutor":      req.ai_tutor_enabled,
    })
    await db.commit()

    return {
        "session_id": session_id,
        "stream_key": stream_key,
        "rtmp_ingest_url":  rtmp_url,
        "hls_playback_url": hls_url,
        "obs_settings": {
            "server":   LIVE_RTMP,
            "stream_key": stream_key,
        },
        "webrtc_url": f"https://live.i3technologies.co.ke/webrtc/publish/{stream_key}",
        "viewer_url": hls_url,
        "status": "scheduled",
        "message": (
            "Session created. Use the RTMP URL in OBS or the WebRTC URL "
            "in the browser to start streaming."
        ),
    }


@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Mark session as live."""
    await db.execute(text("""
        UPDATE live_sessions
        SET status='live', started_at=NOW()
        WHERE id=:id
    """), {"id": session_id})
    await db.commit()
    return {"session_id": session_id, "status": "live"}


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    req: EndSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    End a live session. Optionally trigger n8n VOD pipeline:
      transcribe → chapter detection → subtitles → package → Moodle publish
    """
    row = await db.execute(text("SELECT * FROM live_sessions WHERE id=:id"), {"id": session_id})
    session = row.mappings().first()
    if not session:
        raise HTTPException(404, "Session not found")

    await db.execute(text("""
        UPDATE live_sessions SET status='ended', ended_at=NOW() WHERE id=:id
    """), {"id": session_id})
    await db.commit()

    vod_job_id = None
    if req.trigger_vod:
        vod_job_id = await _trigger_vod_pipeline(dict(session))

    return {
        "session_id":  session_id,
        "status":      "ended",
        "vod_job_id":  vod_job_id,
        "message": (
            "Session ended. VOD pipeline triggered via n8n — "
            "the recording will be transcribed, chaptered, and published to Moodle."
            if req.trigger_vod else "Session ended."
        ),
    }


async def _trigger_vod_pipeline(session: dict) -> Optional[str]:
    """
    Fire n8n webhook to start the post-stream VOD pipeline.
    n8n workflow: recording detected → STT → AI chapters → subtitles → transcode → Moodle
    """
    try:
        payload = {
            "session_id":    session["id"],
            "stream_key":    session["stream_key"],
            "course_id":     str(session.get("course_id") or ""),
            "title":         session["title"],
            "hls_source":    session["hls_url"],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{N8N_URL}/webhook/smartlab-vod-pipeline",
                json=payload,
                headers={"X-N8N-API-KEY": N8N_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"n8n VOD pipeline triggered for session {session['id']}")
            return data.get("execution_id")
    except Exception as e:
        logger.error(f"Failed to trigger n8n VOD pipeline: {e}")
        return None


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.execute(text("SELECT * FROM live_sessions WHERE id=:id"), {"id": session_id})
    session = row.mappings().first()
    if not session:
        raise HTTPException(404, "Session not found")
    return dict(session)


@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    where = "WHERE status=:status" if status else ""
    rows = await db.execute(text(f"""
        SELECT id, title, status, stream_key, hls_url, started_at, ended_at, course_id
        FROM live_sessions {where}
        ORDER BY created_at DESC LIMIT :limit
    """), {"status": status, "limit": limit})
    return {"sessions": [dict(r) for r in rows.mappings()]}
