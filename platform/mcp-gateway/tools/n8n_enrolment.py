"""
MCP Tool: n8n.enrolment.trigger — Tier 2 (customer-facing)

Input schema:
  { student_id: str, email: str, cohort_id: str, evalos_pass_score: float }

Output:
  { success: bool, workflow: str, student: str }
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.n8n.enrolment")

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")

SPEC = McpToolSpec(
    name="n8n.enrolment.trigger",
    description="Fire the n8n auto-enrolment webhook for a student who has passed EvalOS.",
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="customer_facing",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=12_000,
    audit_required=True,
)


async def handle(payload: dict[str, Any], *, tenant_id: str, db=None) -> dict:
    if not N8N_WEBHOOK_URL:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="n8n webhook URL not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(N8N_WEBHOOK_URL, json=payload)
        resp.raise_for_status()

    email    = payload.get("email", "")
    cohort   = payload.get("cohort_id", "")
    log.info("n8n enrolment triggered for %s → cohort %s", email, cohort)
    return {"success": True, "workflow": "auto-enrolment", "student": email}


register_tool(SPEC, handle)
