#!/usr/bin/env python3
"""
Consent Service — STEP-P2-02
Dedicated FastAPI microservice that owns consent_records and consent_audit tables.
Replaces the bare boolean `consent` field used across FORD, Engage, and SIT.

Endpoints:
  POST   /consent                         — record a consent decision
  GET    /consent/{subject_id_hash}       — check consent (default-deny)
  DELETE /consent/{subject_id_hash}       — request right-to-erasure
  GET    /consent/{subject_id_hash}/audit — full audit trail
  GET    /health                          — liveness probe
"""
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas import (
    ConsentAuditResponse,
    ConsentCheckResponse,
    ConsentCreate,
    ConsentCreatedResponse,
    ConsentErasureRequest,
    ConsentErasureResponse,
)

log = logging.getLogger("consent-service")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

DATABASE_URL = os.environ["CONSENT_DB_URL"]
TENANT_HEADER = "X-Tenant-ID"   # Callers MUST supply this header (HC-4)

# ── Connection pool ────────────────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
        statement_cache_size=0,
    )
    log.info("consent-service: asyncpg pool created")
    yield
    if _pool:
        await _pool.close()
    log.info("consent-service: asyncpg pool closed")


app = FastAPI(
    title="i3 Consent Service",
    version="1.0.0",
    description="Data-protection-compliant consent ledger (STEP-P2-02)",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://engage.i3technologies.co.ke",
        "https://evalos.i3technologies.co.ke",
        "https://pmaas.i3technologies.co.ke",
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _set_rls(conn: asyncpg.Connection, tenant_id: uuid.UUID) -> None:
    """Set PostgreSQL session-local `app.tenant_id` for RLS enforcement."""
    await conn.execute("SET LOCAL app.tenant_id = $1", str(tenant_id))


async def _emit_audit(
    conn: asyncpg.Connection,
    *,
    consent_id: Optional[uuid.UUID],
    tenant_id: uuid.UUID,
    event_type: str,
    actor: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Insert a row into consent_audit within the caller's transaction."""
    await conn.execute(
        """
        INSERT INTO consent_audit (id, consent_id, tenant_id, event_type, actor, timestamp, metadata)
        VALUES ($1, $2, $3, $4, $5, now(), $6)
        """,
        uuid.uuid4(),
        consent_id,
        tenant_id,
        event_type,
        actor,
        metadata,
    )


# ── POST /consent ──────────────────────────────────────────────────────────────

@app.post("/consent", response_model=ConsentCreatedResponse, status_code=201)
async def create_consent(body: ConsentCreate):
    """
    Record a consent decision (granted or revoked).
    Emits a consent_audit row within the same transaction.
    HC-4: tenant_id is mandatory in the request body.
    """
    consent_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async with _pool.acquire() as conn:                         # type: ignore[union-attr]
        async with conn.transaction():
            await _set_rls(conn, body.tenant_id)
            await conn.execute(
                """
                INSERT INTO consent_records
                  (id, tenant_id, subject_id_hash, channel, purpose,
                   status, recorded_at, source, expiry, version)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                consent_id,
                body.tenant_id,
                body.subject_id_hash,
                body.channel,
                body.purpose,
                body.status,
                now,
                body.source,
                body.expiry,
                body.version,
            )
            await _emit_audit(
                conn,
                consent_id=consent_id,
                tenant_id=body.tenant_id,
                event_type=body.status,       # "granted" or "revoked"
                actor=body.source,
            )

    log.info(
        "consent_recorded subject=%s channel=%s purpose=%s status=%s tenant=%s",
        body.subject_id_hash[:8] + "…",
        body.channel,
        body.purpose,
        body.status,
        body.tenant_id,
    )
    return ConsentCreatedResponse(consent_id=consent_id, recorded_at=now)


# ── GET /consent/{subject_id_hash} ─────────────────────────────────────────────

@app.get("/consent/{subject_id_hash}", response_model=ConsentCheckResponse)
async def check_consent(
    subject_id_hash: str,
    channel: str = Query(...),
    purpose: str = Query(...),
    tenant_id: uuid.UUID = Query(..., description="HC-4 mandatory tenant scoping"),
):
    """
    Check whether a subject has active consent for a given channel/purpose.
    Default-deny: returns { allowed: false } when no record is found.
    Emits a 'checked' audit event for every call.
    """
    async with _pool.acquire() as conn:                         # type: ignore[union-attr]
        async with conn.transaction():
            await _set_rls(conn, tenant_id)
            row = await conn.fetchrow(
                """
                SELECT id, status, recorded_at, expiry
                FROM consent_records
                WHERE tenant_id = $1
                  AND subject_id_hash = $2
                  AND channel = $3
                  AND purpose = $4
                  AND status = 'granted'
                  AND (expiry IS NULL OR expiry > now())
                ORDER BY recorded_at DESC
                LIMIT 1
                """,
                tenant_id,
                subject_id_hash,
                channel,
                purpose,
            )
            if row:
                await _emit_audit(
                    conn,
                    consent_id=row["id"],
                    tenant_id=tenant_id,
                    event_type="checked",
                    metadata={"channel": channel, "purpose": purpose, "result": "allowed"},
                )
            else:
                await _emit_audit(
                    conn,
                    consent_id=None,
                    tenant_id=tenant_id,
                    event_type="checked",
                    metadata={"channel": channel, "purpose": purpose, "result": "denied"},
                )

    if row:
        return ConsentCheckResponse(
            allowed=True,
            recorded_at=row["recorded_at"],
            expiry=row["expiry"],
        )
    return ConsentCheckResponse(allowed=False)


# ── DELETE /consent/{subject_id_hash} ──────────────────────────────────────────

@app.delete("/consent/{subject_id_hash}", response_model=ConsentErasureResponse)
async def request_erasure(subject_id_hash: str, body: ConsentErasureRequest):
    """
    Right-to-erasure request (GDPR/DPA Art. 17).
    Marks all consent records as 'erased' and queues an erasure job.
    The actual PII wipe is deferred to a background worker (Phase 3).
    """
    erasure_job_id = uuid.uuid4()

    async with _pool.acquire() as conn:                         # type: ignore[union-attr]
        async with conn.transaction():
            await _set_rls(conn, body.tenant_id)
            updated = await conn.fetch(
                """
                UPDATE consent_records
                SET status = 'erased'
                WHERE tenant_id = $1 AND subject_id_hash = $2 AND status != 'erased'
                RETURNING id
                """,
                body.tenant_id,
                subject_id_hash,
            )
            for rec in updated:
                await _emit_audit(
                    conn,
                    consent_id=rec["id"],
                    tenant_id=body.tenant_id,
                    event_type="erased",
                    actor=body.requested_by,
                    metadata={"reason": body.reason, "erasure_job_id": str(erasure_job_id)},
                )

    log.info(
        "consent_erasure_queued subject=%s job=%s by=%s tenant=%s",
        subject_id_hash[:8] + "…",
        erasure_job_id,
        body.requested_by,
        body.tenant_id,
    )
    return ConsentErasureResponse(erasure_job_id=erasure_job_id, status="queued")


# ── GET /consent/{subject_id_hash}/audit ───────────────────────────────────────

@app.get("/consent/{subject_id_hash}/audit", response_model=ConsentAuditResponse)
async def get_audit_trail(
    subject_id_hash: str,
    tenant_id: uuid.UUID = Query(..., description="HC-4 mandatory tenant scoping"),
):
    """
    Return the full audit trail for a subject across all consent records.
    """
    async with _pool.acquire() as conn:                         # type: ignore[union-attr]
        await _set_rls(conn, tenant_id)
        rows = await conn.fetch(
            """
            SELECT a.id, a.consent_id, a.tenant_id, a.event_type,
                   a.actor, a.timestamp, a.metadata
            FROM consent_audit a
            JOIN consent_records r ON a.consent_id = r.id
            WHERE r.tenant_id = $1
              AND r.subject_id_hash = $2
            UNION ALL
            SELECT a2.id, a2.consent_id, a2.tenant_id, a2.event_type,
                   a2.actor, a2.timestamp, a2.metadata
            FROM consent_audit a2
            WHERE a2.tenant_id = $1
              AND a2.consent_id IS NULL
              AND a2.metadata->>'channel' IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 500
            """,
            tenant_id,
            subject_id_hash,
        )

    return ConsentAuditResponse(
        events=[
            dict(
                id=row["id"],
                consent_id=row["consent_id"],
                tenant_id=row["tenant_id"],
                event_type=row["event_type"],
                actor=row["actor"],
                timestamp=row["timestamp"],
                metadata=row["metadata"],
            )
            for row in rows
        ]
    )


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "consent-service", "version": "1.0.0"}
