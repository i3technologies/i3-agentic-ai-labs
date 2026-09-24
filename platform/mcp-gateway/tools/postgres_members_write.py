"""
MCP Tool: postgres.members.write — Tier 3 (PII write — legal/financial class)

This tool performs INSERT/UPDATE on the members table.  Because it touches
Kenyan NID-derived tokens (HC-6) and financial enrolment records, it is
classified at the highest risk tier.

Execution flow:
  1. Agent calls this tool → gateway stages a PENDING approval record and
     returns { pending: true, approval_id, expires_at }.
  2. A human approver calls POST /approvals/{approval_id}/decide
     { status: "APPROVED", note: "..." }.
  3. Agent polls GET /approvals/{approval_id} until APPROVED/DENIED.
  4. Agent re-calls the tool with { approval_id: <uuid> }; gateway
     verifies the signed record and executes the write.

HC-6: Only accepts pre-computed HMAC-SHA256 member_token — never raw NID.
HC-4: tenant_id enforced on every query.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

from fastapi import HTTPException

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.postgres.members.write")

# HC-6: member_token must be a 64-char hex HMAC-SHA256, never raw NID
_TOKEN_RE = re.compile(r"^[0-9a-f]{64}$", re.I)

SPEC = McpToolSpec(
    name="postgres.members.write",
    description=(
        "Write a member record to the platform PostgreSQL members table. "
        "[GAP] Full production asyncpg pool wired at gateway lifespan — "
        "PENDING approval-flow acceptance test before enabling in production."
    ),
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="external_write",
    risk_tier=3,
    rate_limit=10,
    timeout_ms=15_000,
    audit_required=True,
)


async def handle(payload: dict[str, Any], *, tenant_id: str, db=None) -> dict:
    """
    Execute the members write AFTER a signed APPROVED human_approval_record
    has been verified by the gateway interceptor.  By the time this handler
    runs, the gateway has already:
      - loaded the human_approval_record from DB
      - confirmed status == 'APPROVED'
      - confirmed expires_at > now()
      - confirmed payload_digest matches sha256(payload)

    This handler only needs to do the actual DB write.

    ``db`` is the asyncpg.Pool injected by the gateway lifespan (app.state.db).
    """
    # HC-6: Reject raw NIDs — only accept pre-hashed tokens
    member_token = payload.get("member_token", "")
    if not member_token or not _TOKEN_RE.match(member_token):
        raise HTTPException(
            status_code=422,
            detail=(
                "HC-6 VIOLATION: member_token must be a 64-character HMAC-SHA256 hex "
                "string. Raw National IDs are forbidden."
            ),
        )

    # HC-4: tenant_id must be present
    if not tenant_id:
        raise HTTPException(status_code=422, detail="HC-4: tenant_id is required")

    if db is None:
        # [GAP] pool not injected — return stub for integration test
        log.warning("[GAP] db pool not injected; returning stub response")
        return {
            "success": True,
            "member_id": "00000000-0000-0000-0000-000000000000",
            "gap": "db pool not injected — stub response",
        }

    async with db.acquire() as conn:
        # HC-4: set tenant context for RLS
        await conn.execute(f"SET app.tenant_id = '{tenant_id}'")

        row = await conn.fetchrow(
            """
            INSERT INTO members (tenant_id, member_token, full_name, email,
                                 programme, source, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'active')
            ON CONFLICT (member_token) DO UPDATE
               SET full_name  = EXCLUDED.full_name,
                   email      = EXCLUDED.email,
                   programme  = EXCLUDED.programme,
                   status     = EXCLUDED.status,
                   updated_at = now()
            RETURNING id, tenant_id, member_token, status, created_at
            """,
            tenant_id,
            member_token,
            payload.get("full_name", ""),
            payload.get("email", ""),
            payload.get("programme", ""),
            payload.get("source", "mcp-gateway"),
        )

    log.info(
        "postgres.members.write: upserted member %s for tenant %s",
        row["id"],
        tenant_id,
    )
    return {
        "success": True,
        "member_id": str(row["id"]),
        "status": row["status"],
    }


def _payload_digest(payload: dict) -> str:
    """SHA-256 of the canonical JSON representation of the payload."""
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canon.encode()).hexdigest()


register_tool(SPEC, handle)
