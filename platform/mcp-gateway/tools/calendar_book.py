"""
MCP Tool: calendar.book — Tier 2 (customer-facing external)

Input schema:
  { name: str, email: str, preferred_date: str, preferred_time: str, programme?: str }

Output (stage 1 — prepare):
  { requires_confirmation: bool, token: str, summary: str }

Human-in-the-Loop: returns a staged token; caller must confirm via
  POST /tools/calendar.confirm/invoke  { token: str }
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import redis as redis_lib

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.calendar.book")

GOOGLE_CREDS = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "{}")
REDIS_URL    = os.environ.get("REDIS_URL", "redis://localhost:6379")

_redis = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)

SPEC_BOOK = McpToolSpec(
    name="calendar.book",
    description="Stage a Google Calendar appointment booking for human confirmation.",
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="customer_facing",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=15_000,
    audit_required=True,
)

SPEC_CONFIRM = McpToolSpec(
    name="calendar.confirm",
    description="Execute a previously staged calendar booking after human approval.",
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="customer_facing",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=30_000,
    audit_required=True,
)


async def handle_book(payload: dict[str, Any], *, tenant_id: str) -> dict:
    token = str(uuid.uuid4())
    _redis.setex(f"mcp:pending:{token}", 300, json.dumps({
        "action":  "calendar_book",
        "payload": payload,
    }))
    name  = payload.get("name", "")
    email = payload.get("email", "")
    date  = payload.get("preferred_date", "")
    time_ = payload.get("preferred_time", "")
    return {
        "requires_confirmation": True,
        "token":   token,
        "summary": f"Book admissions call for {name} ({email}) on {date} at {time_}",
    }


async def handle_confirm(payload: dict[str, Any], *, tenant_id: str) -> dict:
    import asyncio
    token = payload.get("token", "")
    key   = f"mcp:pending:{token}"
    pipe  = _redis.pipeline()
    pipe.get(key)
    pipe.delete(key)
    raw, _ = pipe.execute()
    if not raw:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Token not found or expired")
    entry = json.loads(raw)
    if entry.get("action") != "calendar_book":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Token action mismatch")

    p = entry["payload"]
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds_data = json.loads(GOOGLE_CREDS)
        creds = Credentials.from_service_account_info(
            creds_data,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )

        def _create():
            service = build("calendar", "v3", credentials=creds)
            event = {
                "summary":     f"i3 Admissions Call — {p['name']}",
                "description": f"Programme interest: {p.get('programme', '')}",
                "start": {"dateTime": f"{p['preferred_date']}T{p['preferred_time']}:00+02:00", "timeZone": "Africa/Nairobi"},
                "end":   {"dateTime": f"{p['preferred_date']}T{p['preferred_time']}:00+02:00", "timeZone": "Africa/Nairobi"},
                "attendees": [{"email": p["email"]}],
            }
            return service.events().insert(calendarId="primary", body=event).execute()

        result = await asyncio.get_event_loop().run_in_executor(None, _create)
        log.info("Calendar event created: %s", result.get("id"))
        return {"success": True, "event_id": result.get("id"), "link": result.get("htmlLink")}
    except Exception as exc:
        log.error("Calendar booking failed: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Calendar booking failed: {exc}") from exc


register_tool(SPEC_BOOK,    handle_book)
register_tool(SPEC_CONFIRM, handle_confirm)
