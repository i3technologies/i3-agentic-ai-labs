"""
MCP Tool: odoo.crm.create — Tier 2 (customer-facing external)
          odoo.crm.read   — Tier 0 (read-only CRM lookup)

Input schema (odoo.crm.create):
  { name: str, email: str, phone?: str, programme?: str, source?: str }

Input schema (odoo.crm.read):
  { email: str }

Output (odoo.crm.create):
  { requires_confirmation: bool, token: str, summary: str }

Output (odoo.crm.read):
  { found: bool, lead?: { id, name, email_from, stage_id } }

Human-in-the-Loop: create returns a staged token; caller must confirm via
  POST /tools/odoo.crm.confirm/invoke  { token: str }
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

import redis as redis_lib

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.odoo.crm")

ODOO_URL      = os.environ.get("ODOO_URL", "")
ODOO_DB       = os.environ.get("ODOO_DB",  "i3_crm")
ODOO_USER     = os.environ.get("ODOO_USERNAME", "")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "")
REDIS_URL     = os.environ.get("REDIS_URL", "redis://localhost:6379")

_redis = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)

SPEC_CREATE = McpToolSpec(
    name="odoo.crm.create",
    description="Stage a new CRM lead for human confirmation before writing to Odoo.",
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="customer_facing",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=15_000,
    audit_required=True,
)

SPEC_READ = McpToolSpec(
    name="odoo.crm.read",
    description="Look up an existing Odoo CRM lead by email.",
    version="1.0.0",
    tenant_scope="single",
    read_write="read",
    side_effect_class="external_read",
    risk_tier=0,
    rate_limit=60,
    timeout_ms=10_000,
    audit_required=False,
)

SPEC_CONFIRM = McpToolSpec(
    name="odoo.crm.confirm",
    description="Execute a previously staged CRM lead creation after human approval.",
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="customer_facing",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=15_000,
    audit_required=True,
)


async def _odoo_authenticate() -> int:
    import xmlrpc.client
    loop = asyncio.get_event_loop()
    def _auth():
        with xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common") as proxy:
            uid = proxy.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if not uid:
            raise RuntimeError("Odoo authentication failed")
        return uid
    return await loop.run_in_executor(None, _auth)


async def _odoo_call(model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
    import xmlrpc.client
    uid = await _odoo_authenticate()
    loop = asyncio.get_event_loop()
    def _call():
        with xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object") as proxy:
            return proxy.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, args, kwargs or {})
    return await loop.run_in_executor(None, _call)


async def handle_create(payload: dict[str, Any], *, tenant_id: str) -> dict:
    token = str(uuid.uuid4())
    _redis.setex(f"mcp:pending:{token}", 300, json.dumps({
        "action":  "odoo_create_lead",
        "payload": payload,
    }))
    name  = payload.get("name", "")
    email = payload.get("email", "")
    prog  = payload.get("programme", "")
    src   = payload.get("source",    "admissions-chatbot")
    return {
        "requires_confirmation": True,
        "token":   token,
        "summary": f"Create CRM lead for {name} ({email}), programme: {prog}, source: {src}",
    }


async def handle_confirm(payload: dict[str, Any], *, tenant_id: str) -> dict:
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
    if entry.get("action") != "odoo_create_lead":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Token action mismatch")
    p       = entry["payload"]
    lead_id = await _odoo_call(
        "crm.lead", "create",
        [{
            "name":         f"Admissions inquiry — {p['name']}",
            "partner_name": p["name"],
            "email_from":   p["email"],
            "phone":        p.get("phone", ""),
            "description":  f"Programme: {p.get('programme','')}\nSource: {p.get('source','')}",
            "tag_ids":      [],
            "source_id":    False,
        }],
    )
    log.info("Created Odoo lead %s for %s", lead_id, p["email"])
    return {"success": True, "lead_id": lead_id}


async def handle_read(payload: dict[str, Any], *, tenant_id: str) -> dict:
    email   = payload.get("email", "")
    records = await _odoo_call(
        "crm.lead", "search_read",
        [[["email_from", "=", email]]],
        {"fields": ["id", "name", "partner_name", "email_from", "stage_id"], "limit": 1},
    )
    if not records:
        return {"found": False}
    return {"found": True, "lead": records[0]}


register_tool(SPEC_CREATE,  handle_create)
register_tool(SPEC_CONFIRM, handle_confirm)
register_tool(SPEC_READ,    handle_read)
