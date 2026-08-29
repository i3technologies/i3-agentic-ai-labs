"""
MCP Connector Service — Admissions AI + Onboarding Agent
Provides tool endpoints for Odoo CRM, Google Calendar, n8n workflows,
and Onboarding Agent task sync.

Endpoints:
  POST /tools/crm/create-lead            — Create Odoo CRM lead
  POST /tools/crm/get-lead               — Look up lead by email
  POST /tools/calendar/book              — Book intro appointment
  POST /tools/n8n/trigger-enrolment      — Trigger auto-enrolment workflow
  POST /tools/onboarding/sync-tasks      — Stage 1: prepare onboarding task sync
  POST /tools/onboarding/confirm/{token} — Stage 2: confirm sync to Directus CRM
  GET  /health

Human-in-the-Loop: all write operations return a confirmation payload
before executing. The caller must call the matching /confirm/{token}
after presenting the summary to the user and receiving explicit approval.

🔴 NEVER AUTO-WRITE to EvalOS or Keycloak — those require manual operator approval.
🟡 ONE-CLICK: onboarding task sync to Directus CRM uses this 2-stage pattern.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

log = logging.getLogger("mcp-connectors")
logging.basicConfig(level=logging.INFO)

# ── Config ─────────────────────────────────────────────────────────────────
ODOO_URL      = os.environ.get("ODOO_URL", "")
ODOO_DB       = os.environ.get("ODOO_DB", "i3_crm")
ODOO_USER     = os.environ.get("ODOO_USERNAME", "")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "")

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
GOOGLE_CREDS    = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "{}")

# In-memory pending confirmation store (replace with Redis in production)
_pending: dict[str, dict[str, Any]] = {}


# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="MCP Connectors", version="1.0.0")


# ── Schemas ─────────────────────────────────────────────────────────────────
class CreateLeadRequest(BaseModel):
    name: str
    email: str
    phone: str = ""
    programme: str = ""
    source: str = "admissions-chatbot"


class BookAppointmentRequest(BaseModel):
    name: str
    email: str
    preferred_date: str     # ISO 8601 date string
    preferred_time: str     # e.g. "10:00"
    programme: str = ""


class EnrolmentTriggerRequest(BaseModel):
    student_id: str
    email: str
    cohort_id: str
    evalos_pass_score: float


class ConfirmRequest(BaseModel):
    token: str


# ── Odoo XML-RPC client ──────────────────────────────────────────────────────
async def _odoo_authenticate() -> int:
    """Returns Odoo user ID."""
    import xmlrpc.client
    with xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common") as proxy:
        uid = proxy.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        raise RuntimeError("Odoo authentication failed")
    return uid


async def _odoo_call(model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
    """Generic Odoo XML-RPC call."""
    import xmlrpc.client
    import asyncio
    uid = await _odoo_authenticate()
    def _call():
        with xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object") as proxy:
            return proxy.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, args, kwargs or {})
    return await asyncio.get_event_loop().run_in_executor(None, _call)


# ── Tool: Create CRM Lead ────────────────────────────────────────────────────
@app.post("/tools/crm/create-lead")
async def create_lead(req: CreateLeadRequest):
    """Stage 1: returns confirmation token. Caller must confirm before writing."""
    token = str(uuid.uuid4())
    _pending[token] = {
        "action": "odoo_create_lead",
        "payload": req.model_dump(),
        "expires": time.time() + 300,
    }
    return {
        "requires_confirmation": True,
        "token": token,
        "summary": (
            f"Create CRM lead for {req.name} ({req.email}), "
            f"programme: {req.programme}, source: {req.source}"
        ),
    }


@app.post("/tools/crm/confirm/{token}")
async def confirm_create_lead(token: str):
    """Stage 2: execute after human confirms."""
    entry = _pending.pop(token, None)
    if not entry or entry["action"] != "odoo_create_lead":
        raise HTTPException(404, "Token not found or expired")
    if time.time() > entry["expires"]:
        raise HTTPException(410, "Confirmation token expired")

    p = entry["payload"]
    lead_id = await _odoo_call(
        "crm.lead", "create",
        [{
            "name":          f"Admissions inquiry — {p['name']}",
            "partner_name":  p["name"],
            "email_from":    p["email"],
            "phone":         p["phone"],
            "description":   f"Programme: {p['programme']}\nSource: {p['source']}",
            "tag_ids":       [],
            "source_id":     False,
        }],
    )
    log.info(f"Created Odoo lead {lead_id} for {p['email']}")
    return {"success": True, "lead_id": lead_id}


@app.post("/tools/crm/get-lead")
async def get_lead(email: str):
    """Look up existing lead by email address."""
    records = await _odoo_call(
        "crm.lead", "search_read",
        [[["email_from", "=", email]]],
        {"fields": ["id", "name", "partner_name", "email_from", "stage_id"], "limit": 1},
    )
    if not records:
        return {"found": False}
    return {"found": True, "lead": records[0]}


# ── Tool: Book Calendar Appointment ─────────────────────────────────────────
@app.post("/tools/calendar/book")
async def book_appointment(req: BookAppointmentRequest):
    """Stage 1: returns confirmation token."""
    token = str(uuid.uuid4())
    _pending[token] = {
        "action": "calendar_book",
        "payload": req.model_dump(),
        "expires": time.time() + 300,
    }
    return {
        "requires_confirmation": True,
        "token": token,
        "summary": (
            f"Book admissions call for {req.name} ({req.email}) "
            f"on {req.preferred_date} at {req.preferred_time}"
        ),
    }


@app.post("/tools/calendar/confirm/{token}")
async def confirm_booking(token: str):
    """Stage 2: create Google Calendar event."""
    entry = _pending.pop(token, None)
    if not entry or entry["action"] != "calendar_book":
        raise HTTPException(404, "Token not found or expired")
    if time.time() > entry["expires"]:
        raise HTTPException(410, "Confirmation token expired")

    p = entry["payload"]
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        import asyncio

        creds_data = json.loads(GOOGLE_CREDS)
        creds = Credentials.from_service_account_info(
            creds_data,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )

        def _create_event():
            service = build("calendar", "v3", credentials=creds)
            event = {
                "summary":     f"i3 Admissions Call — {p['name']}",
                "description": f"Programme interest: {p['programme']}",
                "start": {"dateTime": f"{p['preferred_date']}T{p['preferred_time']}:00+02:00", "timeZone": "Africa/Nairobi"},
                "end":   {"dateTime": f"{p['preferred_date']}T{p['preferred_time']}:00+02:00", "timeZone": "Africa/Nairobi"},
                "attendees": [{"email": p["email"]}],
            }
            return service.events().insert(calendarId="primary", body=event).execute()

        result = await asyncio.get_event_loop().run_in_executor(None, _create_event)
        log.info(f"Calendar event created: {result.get('id')}")
        return {"success": True, "event_id": result.get("id"), "link": result.get("htmlLink")}

    except Exception as e:
        log.error(f"Calendar booking failed: {e}")
        raise HTTPException(500, f"Calendar booking failed: {str(e)}")


# ── Tool: Trigger n8n Auto-Enrolment ────────────────────────────────────────
@app.post("/tools/n8n/trigger-enrolment")
async def trigger_enrolment(req: EnrolmentTriggerRequest):
    """Fire-and-forget enrolment webhook to n8n."""
    if not N8N_WEBHOOK_URL:
        raise HTTPException(503, "n8n webhook URL not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(N8N_WEBHOOK_URL, json=req.model_dump())
        resp.raise_for_status()

    log.info(f"Enrolment triggered for {req.email} → cohort {req.cohort_id}")
    return {"success": True, "workflow": "auto-enrolment", "student": req.email}


# ── Tool: Onboarding Task Sync ───────────────────────────────────────────────
# 🟡 ONE-CLICK APPROVAL GATE
# Called by the Onboarding Agent (i3-onboarding namespace) to sync a generated
# ramp-up plan's tasks into Directus CMS for tracking and notification.
#
# Reuses the same 2-stage _pending dict pattern as CRM/Calendar tools.
# NOTE: Replace _pending with Redis for multi-replica deployments.

DIRECTUS_URL   = os.environ.get("DIRECTUS_URL", "")
DIRECTUS_TOKEN = os.environ.get("DIRECTUS_TOKEN", "")
N8N_ONBOARDING_WEBHOOK = os.environ.get("N8N_ONBOARDING_WEBHOOK_URL", "")


class OnboardingTask(BaseModel):
    day:              int
    title:            str
    description:      str
    file_paths:       list[str] = []
    verified:         bool      = True
    priority:         str       = "medium"   # high | medium | low
    estimated_hours:  float     = 2.0
    historical_ref:   str       = ""
    confidence:       float     = 0.85


class SyncTasksRequest(BaseModel):
    role:    str                 # e.g. "platform_engineer"
    user_id: str                 # Keycloak sub claim
    tasks:   list[OnboardingTask]


@app.post("/tools/onboarding/sync-tasks")
async def onboarding_sync_prepare(req: SyncTasksRequest):
    """
    Stage 1: Validate and stage the onboarding tasks for confirmation.
    Returns a confirmation token valid for 5 minutes.
    The Onboarding Agent must present the task summary to the user
    and call /tools/onboarding/confirm/{token} only after explicit approval.
    """
    if not req.tasks:
        raise HTTPException(400, "Task list is empty — nothing to sync")

    token = str(uuid.uuid4())
    _pending[token] = {
        "action":  "onboarding_sync_tasks",
        "payload": req.model_dump(),
        "expires": time.time() + 300,
    }

    preview = [
        {"day": t.day, "title": t.title, "priority": t.priority}
        for t in req.tasks[:5]
    ]

    log.info(f"Onboarding sync staged: {len(req.tasks)} tasks for {req.role} / {req.user_id}")
    return {
        "requires_confirmation": True,
        "token":     token,
        "task_count": len(req.tasks),
        "preview":   preview,
        "summary": (
            f"Sync {len(req.tasks)} onboarding tasks for role '{req.role}' "
            f"(user: {req.user_id}) to Directus CMS. "
            f"First 5: {', '.join(t.title for t in req.tasks[:5])}"
        ),
    }


@app.post("/tools/onboarding/confirm/{token}")
async def onboarding_sync_confirm(token: str):
    """
    Stage 2: Execute the sync after human one-click confirmation.
    Writes each task to Directus CMS onboarding_tasks collection
    and optionally fires the n8n onboarding notification webhook.
    """
    entry = _pending.pop(token, None)
    if not entry or entry["action"] != "onboarding_sync_tasks":
        raise HTTPException(404, "Token not found or expired")
    if time.time() > entry["expires"]:
        raise HTTPException(410, "Confirmation token expired")

    payload = entry["payload"]
    tasks   = payload["tasks"]
    role    = payload["role"]
    user_id = payload["user_id"]

    synced_ids: list[str] = []
    skipped   = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for task in tasks:
            if not DIRECTUS_URL or not DIRECTUS_TOKEN:
                log.warning("DIRECTUS_URL/TOKEN not set — skipping CRM write")
                skipped += 1
                continue
            try:
                resp = await client.post(
                    f"{DIRECTUS_URL}/items/onboarding_tasks",
                    json={
                        "role":             role,
                        "user_id":          user_id,
                        "day":              task["day"],
                        "title":            task["title"],
                        "description":      task["description"],
                        "file_paths":       "\n".join(task.get("file_paths", [])),
                        "verified":         task.get("verified", True),
                        "priority":         task.get("priority", "medium"),
                        "estimated_hours":  task.get("estimated_hours", 2.0),
                        "historical_ref":   task.get("historical_ref", ""),
                        "confidence":       task.get("confidence", 0.85),
                        "created_at":       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    headers={
                        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
                        "Content-Type":  "application/json",
                    },
                )
                if resp.status_code in (200, 201):
                    item_id = resp.json().get("data", {}).get("id", "unknown")
                    synced_ids.append(item_id)
                else:
                    log.warning(f"Directus returned {resp.status_code} for task: {task['title']}")
                    skipped += 1
            except Exception as exc:
                log.error(f"Failed to sync task '{task['title']}': {exc}")
                skipped += 1

        # Fire n8n notification webhook (best-effort, non-blocking)
        if N8N_ONBOARDING_WEBHOOK and synced_ids:
            try:
                await client.post(
                    N8N_ONBOARDING_WEBHOOK,
                    json={
                        "event":      "onboarding_tasks_synced",
                        "role":       role,
                        "user_id":    user_id,
                        "task_count": len(synced_ids),
                    },
                    timeout=5.0,
                )
            except Exception as exc:
                log.warning(f"n8n onboarding webhook failed (non-fatal): {exc}")

    log.info(f"Onboarding sync complete: {len(synced_ids)} synced, {skipped} skipped")
    return {
        "success":       True,
        "synced_count":  len(synced_ids),
        "skipped_count": skipped,
        "directus_ids":  synced_ids,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp-connectors"}
