"""
MCP Connector Proxy — Admissions AI + Onboarding Agent

MIGRATION NOTE (STEP-P2-04):
  All tool implementations have moved to the MCP Gateway
  (platform/mcp-gateway/). This module is now a thin HTTP proxy that
  forwards tool invocations from the admissions namespace to the gateway.

  Direct Odoo/Calendar/n8n/Directus calls are no longer made from here.

Endpoints (preserved for backward compatibility):
  POST /tools/crm/create-lead            → proxies → mcp-gateway odoo.crm.create
  POST /tools/crm/confirm/{token}        → proxies → mcp-gateway odoo.crm.confirm
  POST /tools/crm/get-lead               → proxies → mcp-gateway odoo.crm.read
  POST /tools/calendar/book              → proxies → mcp-gateway calendar.book
  POST /tools/calendar/confirm/{token}   → proxies → mcp-gateway calendar.confirm
  POST /tools/n8n/trigger-enrolment      → proxies → mcp-gateway n8n.enrolment.prepare
  POST /tools/n8n/confirm-enrolment/{token} → proxies → mcp-gateway n8n.enrolment.confirm
  POST /tools/onboarding/sync-tasks      → proxies → mcp-gateway directus.tasks.write
  POST /tools/onboarding/confirm/{token} → proxies → mcp-gateway directus.tasks.confirm
  GET  /health

Security (FINDING-MCP-1, FINDING-MCP-2):
  - All mutating routes require a valid Keycloak Bearer JWT (RS256).
  - tenant_id is derived from the JWT sub claim — not a static env-var.
  - /tools/n8n/trigger-enrolment is now a 2-stage gate:
      Stage 1 (prepare): returns a confirmation token.
      Stage 2 (confirm): executes the enrolment with the token.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import jwt as pyjwt
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

log = logging.getLogger("mcp-connectors")
logging.basicConfig(level=logging.INFO)

# ── Config ─────────────────────────────────────────────────────────────────
MCP_GATEWAY_URL   = os.environ.get(
    "MCP_GATEWAY_URL",
    "http://mcp-gateway.i3-agent-mesh.svc.cluster.local:8100",
)
AGENT_ID          = os.environ.get("AGENT_ID", "admissions-agent-v1")
FALLBACK_TENANT   = os.environ.get("DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001")
KEYCLOAK_JWKS_URI = os.environ.get(
    "KEYCLOAK_JWKS_URI",
    "https://sso.i3technologies.co.ke/realms/i3/protocol/openid-connect/certs",
)
KEYCLOAK_ISSUER   = os.environ.get(
    "KEYCLOAK_ISSUER",
    "https://sso.i3technologies.co.ke/realms/i3",
)

# ── JWKS key cache (re-fetched at most once per 10 min) ─────────────────────
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0

import time

async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache and (time.monotonic() - _jwks_fetched_at) < 600:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(KEYCLOAK_JWKS_URI)
        resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_fetched_at = time.monotonic()
    return _jwks_cache


# ── JWT validation dependency ────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=True)


class _CallerCtx:
    """Validated caller context extracted from the Keycloak JWT."""
    def __init__(self, sub: str, tenant_id: str, roles: list[str]):
        self.sub       = sub
        self.tenant_id = tenant_id
        self.roles     = roles


async def _require_auth(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> _CallerCtx:
    """Validate Bearer JWT from Keycloak; extract sub, tenant_id, and roles.

    HC-7: DEV_BYPASS_AUTH is permanently forbidden.
    tenant_id is taken from the 'tenant_id' custom claim; falls back to
    DEFAULT_TENANT_ID only when the claim is absent (single-tenant deployments).
    """
    token = creds.credentials
    try:
        jwks = await _get_jwks()
        signing_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(
            next(k for k in jwks["keys"] if k.get("use") == "sig")
        )
        payload = pyjwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=KEYCLOAK_ISSUER,
            options={"verify_exp": True},
        )
    except StopIteration:
        raise HTTPException(status_code=401, detail="No signing key found in JWKS")
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    tenant_id = payload.get("tenant_id") or FALLBACK_TENANT
    realm_roles: list[str] = (
        payload.get("realm_access", {}).get("roles", [])
    )
    return _CallerCtx(sub=payload["sub"], tenant_id=tenant_id, roles=realm_roles)


def _require_role(*allowed: str):
    """Role-gate dependency — place after _require_auth."""
    async def _check(caller: _CallerCtx = Depends(_require_auth)) -> _CallerCtx:
        if not any(r in caller.roles for r in allowed):
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden — required one of: {list(allowed)}",
            )
        return caller
    return _check


# ── Gateway invocation helper ────────────────────────────────────────────────

async def _invoke(
    tool_name: str,
    payload: dict[str, Any],
    tenant_id: str,
    caller_sub: str | None = None,
) -> dict:
    """Forward a tool invocation to the MCP Gateway with caller-derived tenant."""
    correlation_id = str(uuid.uuid4())
    headers = {
        "X-Agent-Id":        AGENT_ID,
        "X-Tenant-Id":       tenant_id,
        "X-Correlation-Id":  correlation_id,
    }
    if caller_sub:
        headers["X-Caller-Sub"] = caller_sub
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{MCP_GATEWAY_URL}/tools/{tool_name}/invoke",
            headers=headers,
            json={"input": payload},
        )
        if resp.status_code == 403:
            raise HTTPException(status_code=403, detail=resp.json().get("detail", "Forbidden"))
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=resp.json().get("detail", "Not found"))
        resp.raise_for_status()
        return resp.json().get("output", {})


# ── App ─────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    log.info("MCP Connector Proxy started — gateway: %s", MCP_GATEWAY_URL)
    yield


app = FastAPI(title="MCP Connectors (Gateway Proxy)", version="2.0.0", lifespan=lifespan)


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
    preferred_date: str
    preferred_time: str
    programme: str = ""


class EnrolmentTriggerRequest(BaseModel):
    student_id: str
    email: str
    cohort_id: str
    evalos_pass_score: float


class OnboardingTask(BaseModel):
    day:             int
    title:           str
    description:     str
    file_paths:      list[str] = []
    verified:        bool      = True
    priority:        str       = "medium"
    estimated_hours: float     = 2.0
    historical_ref:  str       = ""
    confidence:      float     = 0.85


class SyncTasksRequest(BaseModel):
    role:    str
    user_id: str
    tasks:   list[OnboardingTask]


# ── Routes — CRM ─────────────────────────────────────────────────────────────
@app.post("/tools/crm/create-lead")
async def create_lead(
    req: CreateLeadRequest,
    caller: _CallerCtx = Depends(_require_auth),
):
    return await _invoke("odoo.crm.create", req.model_dump(), caller.tenant_id, caller.sub)


@app.post("/tools/crm/confirm/{token}")
async def confirm_create_lead(
    token: str,
    caller: _CallerCtx = Depends(_require_auth),
):
    return await _invoke("odoo.crm.confirm", {"token": token}, caller.tenant_id, caller.sub)


@app.post("/tools/crm/get-lead")
async def get_lead(
    email: str,
    caller: _CallerCtx = Depends(_require_auth),
):
    return await _invoke("odoo.crm.read", {"email": email}, caller.tenant_id, caller.sub)


# ── Routes — Calendar ─────────────────────────────────────────────────────────
@app.post("/tools/calendar/book")
async def book_appointment(
    req: BookAppointmentRequest,
    caller: _CallerCtx = Depends(_require_auth),
):
    return await _invoke("calendar.book", req.model_dump(), caller.tenant_id, caller.sub)


@app.post("/tools/calendar/confirm/{token}")
async def confirm_booking(
    token: str,
    caller: _CallerCtx = Depends(_require_auth),
):
    return await _invoke("calendar.confirm", {"token": token}, caller.tenant_id, caller.sub)


# ── Routes — n8n ─────────────────────────────────────────────────────────────
# FINDING-MCP-2: enrolment is now a 2-stage gate (prepare → confirm).
# Stage 1: returns a pending confirmation token — no enrolment is triggered yet.
# Stage 2: caller supplies the token to confirm-enrolment to execute.
# Required role: i3-admin (irreversible action, HC-3 / HC-5).

@app.post("/tools/n8n/trigger-enrolment")
async def trigger_enrolment(
    req: EnrolmentTriggerRequest,
    caller: _CallerCtx = Depends(_require_role("i3-admin")),
):
    """Stage 1: prepare an enrolment — returns a confirmation token."""
    return await _invoke("n8n.enrolment.prepare", req.model_dump(), caller.tenant_id, caller.sub)


@app.post("/tools/n8n/confirm-enrolment/{token}")
async def confirm_enrolment(
    token: str,
    caller: _CallerCtx = Depends(_require_role("i3-admin")),
):
    """Stage 2: execute the enrolment after human confirmation of the token."""
    return await _invoke("n8n.enrolment.confirm", {"token": token}, caller.tenant_id, caller.sub)


# ── Routes — Onboarding ───────────────────────────────────────────────────────
@app.post("/tools/onboarding/sync-tasks")
async def onboarding_sync_prepare(
    req: SyncTasksRequest,
    caller: _CallerCtx = Depends(_require_auth),
):
    return await _invoke("directus.tasks.write", req.model_dump(), caller.tenant_id, caller.sub)


@app.post("/tools/onboarding/confirm/{token}")
async def onboarding_sync_confirm(
    token: str,
    caller: _CallerCtx = Depends(_require_auth),
):
    return await _invoke("directus.tasks.confirm", {"token": token}, caller.tenant_id, caller.sub)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp-connectors-proxy", "gateway": MCP_GATEWAY_URL}


@app.get("/health/auth")
async def health_auth(caller: _CallerCtx = Depends(_require_auth)):
    """Authenticated health check — verifies JWT path is operational."""
    return {"status": "ok", "sub": caller.sub, "tenant_id": caller.tenant_id}
