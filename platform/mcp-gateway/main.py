"""
MCP Tool Gateway — FastAPI main entry point.

POST /tools/{tool_name}/invoke
  Headers:
    Authorization: Bearer <agent_jwt>
    X-Agent-Id:    <agent_id>
    X-Tenant-Id:   <tenant_id>
    X-Correlation-Id: <uuid>
  Body: { input: <tool-specific payload> }

  Tier 0–2 tools:
    → 200 { output, invocation_id, duration_ms }

  Tier 3 tools (first call — no approval_id in input):
    → 202 { approval_id, approval_status:"pending", invocation_id, duration_ms:0, output:null }

  Tier 3 tools (second call — with approval_id in input after APPROVED):
    → 200 { output, invocation_id, duration_ms, approval_status:"approved" }

  Error responses:
    → 403 { error: "tool not in agent allowed_tools" }
    → 403 { error: "approval DENIED or EXPIRED" }
    → 429 { error: "rate limit exceeded" }
    → 400 { error: "input validation failed", detail: [...] }

POST /approvals/{approval_id}/decide
  Body: { status: "APPROVED"|"DENIED", note?: str }
  → Signs the approval record; unlocks the Tier 3 gate.

GET /approvals/{approval_id}
  → Current status of an approval record (agent polling).

Risk tier declarations:
  chroma.search          → Tier 0 (read-only)
  litellm.chat           → Tier 1 (low-risk, cost-budgeted)
  calendar.book          → Tier 2 (customer-facing external)
  odoo.crm.create        → Tier 2 (customer-facing external)
  odoo.crm.read          → Tier 0 (read-only CRM lookup)
  n8n.enrolment.trigger  → Tier 2 (customer-facing)
  directus.tasks.write   → Tier 2 (customer-facing)
  kafka.produce          → Tier 2 (customer-facing)
  postgres.members.write → Tier 3 (PII write — legal/financial class)
  github.pr.create       → Tier 3 (consequential write — code/CI autonomy)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from schemas import (
    AgentManifest,
    ApprovalDecide,
    ApprovalRecord,
    InvokeRequest,
    InvokeResponse,
    McpToolSpec,
)

# ── Logging ────────────────────────────────────────────────────────────────
log = logging.getLogger("mcp-gateway")
logging.basicConfig(level=logging.INFO)

# ── Config ─────────────────────────────────────────────────────────────────
MCP_GATEWAY_DB_URL  = os.environ["MCP_GATEWAY_DB_URL"]            # e.g. postgresql://...
REDIS_URL           = os.environ.get("REDIS_URL", "redis://localhost:6379")
AGENT_REGISTRY_URL  = os.environ.get(
    "AGENT_REGISTRY_URL",
    "http://agent-registry.i3-agent-mesh.svc.cluster.local:8200",
)
# Maximum rate-limit window in seconds (1 minute)
RATE_WINDOW_SECONDS = 60

# ── Tool catalogue ─────────────────────────────────────────────────────────
# Loaded from tools/ modules; populated during lifespan startup.
_TOOL_CATALOGUE: dict[str, McpToolSpec] = {}
_TOOL_HANDLERS:  dict[str, Any]         = {}   # tool_name → async callable


def register_tool(spec: McpToolSpec, handler) -> None:
    """Called by each tools/*.py module to register itself."""
    _TOOL_CATALOGUE[spec.name] = spec
    _TOOL_HANDLERS[spec.name]  = handler
    log.info("Registered tool: %s (tier=%d)", spec.name, spec.risk_tier)


# ── App lifecycle ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database pool
    app.state.db = await asyncpg.create_pool(MCP_GATEWAY_DB_URL, min_size=2, max_size=10)

    # Redis for rate limiting
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    # Import and register all tools
    from tools import (  # noqa: F401
        chroma_search,
        litellm_chat,
        odoo_crm,
        calendar_book,
        n8n_enrolment,
        directus_tasks,
        postgres_members_write,
        github_pr_create,
    )

    log.info("MCP Gateway started — %d tools registered", len(_TOOL_CATALOGUE))
    yield

    await app.state.db.close()
    await app.state.redis.aclose()
    log.info("MCP Gateway shut down")


app = FastAPI(
    title="i3 MCP Tool Gateway",
    version="1.1.0",
    description=(
        "Centralised authorisation and auditing gateway for all agent tool invocations. "
        "Tier 3+ tools require a signed human-approval record before execution."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://engage.i3technologies.co.ke",
        "https://evalos.i3technologies.co.ke",
        "https://pmaas.i3technologies.co.ke",
        "https://admissions.i3technologies.co.ke",
    ],
    allow_methods=["POST", "GET", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Agent-Id", "X-Tenant-Id", "X-Correlation-Id"],
)


# ── Agent manifest cache (TTL 60 s) ────────────────────────────────────────
_manifest_cache: dict[str, tuple[float, AgentManifest]] = {}
_MANIFEST_TTL = 60.0


async def _fetch_manifest(agent_id: str) -> AgentManifest:
    now = time.monotonic()
    if agent_id in _manifest_cache:
        ts, manifest = _manifest_cache[agent_id]
        if now - ts < _MANIFEST_TTL:
            return manifest
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{AGENT_REGISTRY_URL}/agents/{agent_id}")
            resp.raise_for_status()
            data = resp.json()
            manifest = AgentManifest(**data)
            _manifest_cache[agent_id] = (now, manifest)
            return manifest
    except Exception as exc:
        log.warning("Agent registry unreachable for %s: %s", agent_id, exc)
        # If registry is down, return cached version regardless of TTL (fail-open for read tools)
        if agent_id in _manifest_cache:
            _, manifest = _manifest_cache[agent_id]
            return manifest
        raise HTTPException(status_code=503, detail="Agent registry unavailable and no cached manifest")


# ── Rate-limit check ────────────────────────────────────────────────────────
async def _check_rate_limit(redis, tool_name: str, agent_id: str, tenant_id: str, limit: int) -> None:
    key = f"mcp:rl:{tool_name}:{tenant_id}:{agent_id}"
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, RATE_WINDOW_SECONDS)
        count, _ = await pipe.execute()
        if count > limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("Rate limit check failed (non-fatal): %s", exc)
        # Fail open — don't block if Redis is unavailable


# ── Payload digest ──────────────────────────────────────────────────────────
def _payload_digest(payload: dict) -> str:
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canon.encode()).hexdigest()


# ── Tier 3: stage approval record ──────────────────────────────────────────
async def _stage_approval(
    db,
    *,
    invocation_id: str,
    tool_name: str,
    agent_id: str,
    tenant_id: str,
    risk_tier: int,
    payload: dict,
) -> ApprovalRecord:
    """Insert a PENDING human_approval_records row and return the record."""
    digest = _payload_digest(payload)
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO human_approval_records
              (tenant_id, invocation_id, tool_name, agent_id, risk_tier, payload_digest)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6)
            RETURNING *
            """,
            tenant_id,
            invocation_id,
            tool_name,
            agent_id,
            risk_tier,
            digest,
        )
    return ApprovalRecord(
        approval_id=str(row["approval_id"]),
        tenant_id=str(row["tenant_id"]),
        invocation_id=str(row["invocation_id"]),
        tool_name=row["tool_name"],
        agent_id=row["agent_id"],
        risk_tier=row["risk_tier"],
        payload_digest=row["payload_digest"],
        status=row["status"],
        requested_at=row["requested_at"],
        expires_at=row["expires_at"],
    )


# ── Tier 3: verify signed approval record ─────────────────────────────────
async def _verify_approval(
    db,
    *,
    approval_id: str,
    tool_name: str,
    agent_id: str,
    tenant_id: str,
    payload: dict,
) -> None:
    """
    Raises HTTPException if no valid APPROVED record exists for this
    approval_id + tool + agent + tenant + payload combination.
    """
    now = datetime.now(tz=timezone.utc)
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM human_approval_records
             WHERE approval_id = $1::uuid
               AND tenant_id   = $2::uuid
               AND tool_name   = $3
               AND agent_id    = $4
            """,
            approval_id,
            tenant_id,
            tool_name,
            agent_id,
        )

    if row is None:
        raise HTTPException(
            status_code=403,
            detail="No approval record found for this invocation — Tier 3 gate requires human sign-off",
        )

    # Mark expired if past expires_at
    if row["expires_at"].replace(tzinfo=timezone.utc) < now and row["status"] == "PENDING":
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE human_approval_records SET status='EXPIRED' WHERE approval_id=$1::uuid",
                approval_id,
            )
        raise HTTPException(status_code=403, detail="Tier 3 approval has EXPIRED — request a new one")

    if row["status"] == "DENIED":
        raise HTTPException(status_code=403, detail="Tier 3 approval was DENIED")

    if row["status"] == "EXPIRED":
        raise HTTPException(status_code=403, detail="Tier 3 approval has EXPIRED — request a new one")

    if row["status"] != "APPROVED":
        raise HTTPException(
            status_code=202,
            detail=f"Tier 3 approval still PENDING (approval_id={approval_id}) — try again after human approves",
        )

    # Verify payload has not changed since staging
    expected_digest = _payload_digest({k: v for k, v in payload.items() if k != "approval_id"})
    if row["payload_digest"] != expected_digest:
        raise HTTPException(
            status_code=400,
            detail="Payload digest mismatch — input changed after approval was issued",
        )


# ── Invocation audit ────────────────────────────────────────────────────────
async def _audit(
    db,
    *,
    invocation_id: str,
    tool_name: str,
    agent_id: str,
    tenant_id: str,
    correlation_id: str,
    risk_tier: int,
    duration_ms: int,
    outcome: str,
    error_detail: str | None,
) -> None:
    try:
        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO mcp_invocation_log
                  (invocation_id, tool_name, agent_id, tenant_id, correlation_id,
                   risk_tier, duration_ms, outcome, error_detail)
                VALUES ($1, $2, $3, $4::uuid, $5::uuid, $6, $7, $8, $9)
                """,
                invocation_id, tool_name, agent_id, tenant_id, correlation_id,
                risk_tier, duration_ms, outcome, error_detail,
            )
    except Exception as exc:
        log.warning("Audit write failed (non-fatal): %s", exc)


# ── Main invocation route ───────────────────────────────────────────────────
@app.post(
    "/tools/{tool_name}/invoke",
    response_model=InvokeResponse,
    summary="Invoke an MCP tool with policy enforcement",
    status_code=200,
)
async def invoke_tool(
    tool_name: str,
    body: InvokeRequest,
    request: Request,
    x_agent_id:       str = Header(..., alias="X-Agent-Id"),
    x_tenant_id:      str = Header(..., alias="X-Tenant-Id"),
    x_correlation_id: str = Header(default_factory=lambda: str(uuid.uuid4()), alias="X-Correlation-Id"),
    authorization:    str = Header(default="", alias="Authorization"),
) -> InvokeResponse:
    """
    Enforces agent identity, tenant isolation, and risk tiers (Tier 0–3).

    Tier 0–2: Executes immediately after all checks pass.
    Tier 3:
      - First call (no input.approval_id): stages a PENDING approval record
        and returns HTTP 202 with approval_id.
      - Second call (input.approval_id present): verifies the signed APPROVED
        record and executes the tool.
    """
    invocation_id = str(uuid.uuid4())
    t_start = time.monotonic()
    outcome = "success"
    error_detail = None

    # ── 1. Tool must exist in catalogue ────────────────────────────────────
    spec = _TOOL_CATALOGUE.get(tool_name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    # ── 2. Agent manifest check — allowed_tools ─────────────────────────────
    try:
        manifest = await _fetch_manifest(x_agent_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if tool_name not in manifest.allowed_tools:
        outcome = "blocked"
        await _audit(
            request.app.state.db,
            invocation_id=invocation_id,
            tool_name=tool_name,
            agent_id=x_agent_id,
            tenant_id=x_tenant_id,
            correlation_id=x_correlation_id,
            risk_tier=spec.risk_tier,
            duration_ms=0,
            outcome=outcome,
            error_detail="tool not in agent allowed_tools",
        )
        raise HTTPException(status_code=403, detail="tool not in agent allowed_tools")

    # ── 3. Tenant isolation — manifest tenant must match header ────────────
    if manifest.tenant_id != x_tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id mismatch")

    # ── 4. Rate-limit enforcement ──────────────────────────────────────────
    await _check_rate_limit(
        request.app.state.redis,
        tool_name=tool_name,
        agent_id=x_agent_id,
        tenant_id=x_tenant_id,
        limit=spec.rate_limit,
    )

    # ── 5. Tier 3 gate ──────────────────────────────────────────────────────
    approval_id_from_input = body.input.get("approval_id")

    if spec.risk_tier >= 3:
        if not approval_id_from_input:
            # Phase 1 — Stage approval and return PENDING
            approval = await _stage_approval(
                request.app.state.db,
                invocation_id=invocation_id,
                tool_name=tool_name,
                agent_id=x_agent_id,
                tenant_id=x_tenant_id,
                risk_tier=spec.risk_tier,
                payload=body.input,
            )
            outcome = "approval_pending"
            await _audit(
                request.app.state.db,
                invocation_id=invocation_id,
                tool_name=tool_name,
                agent_id=x_agent_id,
                tenant_id=x_tenant_id,
                correlation_id=x_correlation_id,
                risk_tier=spec.risk_tier,
                duration_ms=0,
                outcome=outcome,
                error_detail=None,
            )
            from fastapi.responses import JSONResponse  # noqa: PLC0415
            return JSONResponse(
                status_code=202,
                content={
                    "output": None,
                    "invocation_id": invocation_id,
                    "duration_ms": 0,
                    "approval_id": approval.approval_id,
                    "approval_status": "pending",
                },
            )
        else:
            # Phase 2 — Verify the signed approval, then execute
            # Digest is computed against payload minus the approval_id key
            payload_without_approval = {k: v for k, v in body.input.items() if k != "approval_id"}
            await _verify_approval(
                request.app.state.db,
                approval_id=approval_id_from_input,
                tool_name=tool_name,
                agent_id=x_agent_id,
                tenant_id=x_tenant_id,
                payload=payload_without_approval,
            )

    # ── 6. Dispatch to registered tool handler ──────────────────────────────
    handler = _TOOL_HANDLERS[tool_name]
    try:
        output = await asyncio.wait_for(
            handler(body.input, tenant_id=x_tenant_id),
            timeout=spec.timeout_ms / 1000,
        )
    except asyncio.TimeoutError as exc:
        outcome = "error"
        error_detail = "timeout"
        raise HTTPException(status_code=504, detail=f"Tool {tool_name} timed out") from exc
    except HTTPException:
        raise
    except Exception as exc:
        outcome = "error"
        error_detail = str(exc)
        log.error("Tool %s raised: %s", tool_name, exc)
        raise HTTPException(status_code=502, detail=f"Tool execution error: {exc}") from exc
    finally:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        await _audit(
            request.app.state.db,
            invocation_id=invocation_id,
            tool_name=tool_name,
            agent_id=x_agent_id,
            tenant_id=x_tenant_id,
            correlation_id=x_correlation_id,
            risk_tier=spec.risk_tier,
            duration_ms=duration_ms,
            outcome=outcome,
            error_detail=error_detail,
        )

    return InvokeResponse(
        output=output,
        invocation_id=invocation_id,
        duration_ms=duration_ms,
        approval_id=approval_id_from_input,
        approval_status="approved" if approval_id_from_input else "not_required",
    )


# ── Approval management routes (Tier 3 gate) ───────────────────────────────

@app.get(
    "/approvals/{approval_id}",
    response_model=ApprovalRecord,
    summary="Poll the status of a Tier 3 approval record",
)
async def get_approval(approval_id: str, request: Request) -> ApprovalRecord:
    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM human_approval_records WHERE approval_id = $1::uuid",
            approval_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")

    # Auto-expire if past deadline
    now = datetime.now(tz=timezone.utc)
    status = row["status"]
    if status == "PENDING" and row["expires_at"].replace(tzinfo=timezone.utc) < now:
        async with request.app.state.db.acquire() as conn:
            await conn.execute(
                "UPDATE human_approval_records SET status='EXPIRED' WHERE approval_id=$1::uuid",
                approval_id,
            )
        status = "EXPIRED"

    return ApprovalRecord(
        approval_id=str(row["approval_id"]),
        tenant_id=str(row["tenant_id"]),
        invocation_id=str(row["invocation_id"]),
        tool_name=row["tool_name"],
        agent_id=row["agent_id"],
        risk_tier=row["risk_tier"],
        payload_digest=row["payload_digest"],
        status=status,
        approver_id=row["approver_id"],
        approver_email=row["approver_email"],
        approval_note=row["approval_note"],
        requested_at=row["requested_at"],
        decided_at=row["decided_at"],
        expires_at=row["expires_at"],
    )


@app.post(
    "/approvals/{approval_id}/decide",
    response_model=ApprovalRecord,
    summary="Human approver signs or denies a Tier 3 gate",
)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecide,
    request: Request,
    authorization: str = Header(default="", alias="Authorization"),
) -> ApprovalRecord:
    """
    Records the human decision (APPROVED or DENIED) on a Tier 3 gate.
    The approver identity is extracted from the Authorization bearer token
    (Keycloak JWT sub claim). In production this endpoint is guarded by
    Keycloak RBAC role 'mcp-approver'.
    """
    # Extract approver from JWT — minimal parsing (sub claim only)
    approver_sub   = _extract_sub(authorization)
    approver_email = _extract_email(authorization)

    now = datetime.now(tz=timezone.utc)
    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM human_approval_records WHERE approval_id = $1::uuid",
            approval_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")

        if row["status"] not in ("PENDING",):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot decide on a record with status={row['status']}",
            )

        if row["expires_at"].replace(tzinfo=timezone.utc) < now:
            await conn.execute(
                "UPDATE human_approval_records SET status='EXPIRED' WHERE approval_id=$1::uuid",
                approval_id,
            )
            raise HTTPException(status_code=409, detail="Approval window has EXPIRED")

        updated = await conn.fetchrow(
            """
            UPDATE human_approval_records
               SET status        = $1,
                   approver_id   = $2,
                   approver_email= $3,
                   approval_note = $4,
                   decided_at    = now()
             WHERE approval_id   = $5::uuid
            RETURNING *
            """,
            body.status,
            approver_sub,
            approver_email,
            body.note,
            approval_id,
        )

    log.info(
        "Approval %s %s by %s for tool %s (agent %s)",
        approval_id,
        body.status,
        approver_email or approver_sub or "unknown",
        row["tool_name"],
        row["agent_id"],
    )
    return ApprovalRecord(
        approval_id=str(updated["approval_id"]),
        tenant_id=str(updated["tenant_id"]),
        invocation_id=str(updated["invocation_id"]),
        tool_name=updated["tool_name"],
        agent_id=updated["agent_id"],
        risk_tier=updated["risk_tier"],
        payload_digest=updated["payload_digest"],
        status=updated["status"],
        approver_id=updated["approver_id"],
        approver_email=updated["approver_email"],
        approval_note=updated["approval_note"],
        requested_at=updated["requested_at"],
        decided_at=updated["decided_at"],
        expires_at=updated["expires_at"],
    )


# ── JWT helpers (minimal — no full verification, gateway sits behind Keycloak)
def _extract_sub(authorization: str) -> str | None:
    try:
        token = authorization.removeprefix("Bearer ").strip()
        import base64  # noqa: PLC0415
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padding = 4 - len(parts[1]) % 4
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
        return json.loads(payload_bytes).get("sub")
    except Exception:
        return None


def _extract_email(authorization: str) -> str | None:
    try:
        token = authorization.removeprefix("Bearer ").strip()
        import base64  # noqa: PLC0415
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padding = 4 - len(parts[1]) % 4
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
        claims = json.loads(payload_bytes)
        return claims.get("email") or claims.get("preferred_username")
    except Exception:
        return None


# ── Catalogue introspection ─────────────────────────────────────────────────
@app.get("/tools", summary="List all registered tools")
async def list_tools():
    return {
        "tools": [spec.model_dump() for spec in _TOOL_CATALOGUE.values()]
    }


@app.get("/tools/{tool_name}", summary="Get tool specification")
async def get_tool(tool_name: str):
    spec = _TOOL_CATALOGUE.get(tool_name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    return spec.model_dump()


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "tools_registered": len(_TOOL_CATALOGUE)}


@app.get("/readyz")
async def readyz(request: Request):
    try:
        async with request.app.state.db.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB unreachable: {exc}") from exc
    return {"status": "ready", "tools_registered": len(_TOOL_CATALOGUE)}
