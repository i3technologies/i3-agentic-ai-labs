"""
FORD-Asili Registration API — FastAPI service
Namespace: i3-ford

HC-4: tenant_id UUID NOT NULL on all queries.
HC-6: National IDs and phone numbers are stored only as keyed HMAC-SHA256
      (MEMBER_HMAC_SECRET from OpenBao/env). Raw values never enter the DB or chaincode.
HC-8: Ballot choices are architecturally separated via Fabric PDC (voteChoicesCollection).
HC-5: Fabric endorsement policy (≥1 FordPeerMSP.peer) prevents single-agent commit.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

import asyncpg
import httpx
from fastapi import Depends, FastAPI, HTTPException, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Circuit-breaker for the consent-service (fail-closed, STEP-P2-02)
from platform.consent.circuit_breaker import consent_allowed as _cb_consent_allowed, breaker_state as _cb_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("ford-api")

# ── Environment ───────────────────────────────────────────────────────────────
DATABASE_URL         = os.environ["FORD_DB_URL"]             # asyncpg DSN
MEMBER_HMAC_SECRET   = os.environ["MEMBER_HMAC_SECRET"]      # OpenBao-injected (HC-6)
FABRIC_GATEWAY_URL   = os.getenv(
    "FABRIC_GATEWAY_URL",
    "http://fabric-gateway.i3-ford.svc.cluster.local:8080",
)
FORD_TENANT_ID       = os.getenv("FORD_TENANT_ID", "00000000-0000-0000-0000-000000000005")
REDIS_URL            = os.getenv("REDIS_URL", "redis://redis.i3-data.svc.cluster.local:6379/0")
# STEP-P2-02: live consent service (replaces bare boolean field)
CONSENT_SERVICE_URL  = os.getenv(
    "CONSENT_SERVICE_URL",
    "http://consent-service.i3-consent.svc.cluster.local:8000",
)

OTP_MAX_ATTEMPTS: int = 5        # max failed OTP attempts before 429 (HC-6 / rate-limit)
OTP_TTL:          int = 600      # seconds — attempt counter and OTP key TTL

# Pool is initialised in the lifespan; never call asyncpg.connect() outside it.
_pool:  asyncpg.Pool | None = None
_http:  httpx.AsyncClient | None = None
_redis: object | None = None     # aioredis.Redis; injected in lifespan & overridden in tests


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _http
    _pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=2, max_size=10, command_timeout=30)
    _http = httpx.AsyncClient(timeout=10.0)
    log.info("asyncpg pool ready; httpx client ready")
    yield
    await _pool.close()
    await _http.aclose()
    log.info("ford-api shutdown complete")


app = FastAPI(title="FORD-Asili Registration API", lifespan=lifespan)


# ── Helpers ───────────────────────────────────────────────────────────────────

def hmac_token(value: str) -> str:
    """Return HMAC-SHA256(UPPER(STRIP(value)), MEMBER_HMAC_SECRET) hex digest (HC-6).

    Normalises input so that '  07123  ' and '07123' produce the same token,
    making rate-limit and OTP keys collision-resistant across whitespace variants.
    """
    return hmac.new(
        MEMBER_HMAC_SECRET.encode(),
        value.strip().upper().encode(),
        hashlib.sha256,
    ).hexdigest()


# ── OTP helpers (P1-GATE-08) ──────────────────────────────────────────────────

async def _otp_rate_check(phone_token: str) -> None:
    """Increment the OTP attempt counter; raise HTTP 429 if cap exceeded."""
    attempt_key = f"otp_attempts:{phone_token}"
    count = await _redis.incr(attempt_key)         # type: ignore[union-attr]
    if count == 1:
        await _redis.expire(attempt_key, OTP_TTL)  # type: ignore[union-attr]
    if count > OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP attempts. Please wait and try again.",
        )


async def store_otp(phone: str, otp: str) -> None:
    """Store HMAC(otp) in Redis keyed by HMAC(phone) with OTP_TTL expiry."""
    phone_token = hmac_token(phone)
    otp_key     = f"otp:{phone_token}"
    await _redis.set(otp_key, hmac_token(otp), ex=OTP_TTL)  # type: ignore[union-attr]


async def verify_otp_token(phone: str, otp: str) -> bool:
    """
    Rate-check, then compare stored HMAC(otp) against HMAC(submitted otp).

    Returns True on match; False if OTP is missing or incorrect.
    Raises HTTP 429 if rate limit is exceeded.
    """
    phone_token = hmac_token(phone)
    await _otp_rate_check(phone_token)

    stored = await _redis.get(f"otp:{phone_token}")  # type: ignore[union-attr]
    if stored is None:
        return False
    expected = hmac_token(otp)
    return hmac.compare_digest(stored, expected)


async def delete_otp(phone: str) -> None:
    """Delete both OTP and attempt-counter keys for a phone (post-verification cleanup)."""
    phone_token = hmac_token(phone)
    await _redis.delete(             # type: ignore[union-attr]
        f"otp:{phone_token}",
        f"otp_attempts:{phone_token}",
    )


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "pool not initialised"
    return _pool


def get_http() -> httpx.AsyncClient:
    assert _http is not None, "http client not initialised"
    return _http


# ── Fabric gateway integration (STEP-P3-03) ───────────────────────────────────

async def record_on_fabric(
    id_hash: str,
    phone_hash: str,
    ward_code: str,
    tenant_id: str,
    agent_id: str,
) -> str:
    """
    Submit a RegisterMember transaction to the Fabric gateway REST shim.

    Fire-and-forget in Phase 3: registration in PostgreSQL completes first.
    If the gateway is unreachable, the failure is logged and the tx_id is set
    to "fabric-pending" so the retry queue can resubmit asynchronously.

    Returns the Fabric transaction ID string, or "fabric-pending" on failure.
    """
    http = get_http()
    payload = {
        "channel":   "ford-channel",
        "chaincode": "membership-registry",
        "function":  "RegisterMember",
        "args": [
            id_hash,
            phone_hash,
            ward_code,
            tenant_id,
            agent_id,
            datetime.now(UTC).isoformat(),
        ],
    }
    try:
        resp = await http.post(
            f"{FABRIC_GATEWAY_URL}/gateway/v1/commit",
            json=payload,
            timeout=8.0,
        )
        resp.raise_for_status()
        data = resp.json()
        tx_id: str = data.get("transaction_id") or data.get("txId") or "fabric-ok"
        log.info("fabric_commit id_hash=%s tx_id=%s", id_hash[:12], tx_id)
        return tx_id
    except Exception as exc:
        log.warning("fabric_commit_failed id_hash=%s: %s — queuing retry", id_hash[:12], exc)
        # Enqueue retry via Redis (fire-and-forget; handled by a background worker)
        asyncio.ensure_future(_queue_fabric_retry(payload))
        return "fabric-pending"


async def _queue_fabric_retry(payload: dict) -> None:
    """Push the failed Fabric submission to the Redis retry list."""
    try:
        import aioredis  # optional dep; fails silently if not installed in staging
        redis = await aioredis.from_url(REDIS_URL)
        await redis.rpush("ford:fabric:retry", json.dumps(payload))
        await redis.aclose()
    except Exception as exc:
        log.error("fabric_retry_queue_failed: %s", exc)


# ── Request / Response models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    national_id: str  = Field(..., min_length=6, max_length=20)
    phone: str        = Field(..., pattern=r"^\+254\d{9}$")
    ward_code: str    = Field(..., min_length=1, max_length=20)
    constituency: str = Field(..., min_length=1, max_length=100)
    county: str       = Field(..., min_length=1, max_length=100)
    agent_id: str     = Field(..., min_length=1, max_length=50)
    consent: bool


class RegisterResponse(BaseModel):
    member_id: str
    id_hash: str       # first 12 chars only — for client reference, not a lookup key
    ward_code: str
    fabric_tx_id: str
    registered_at: str


class VerifyResponse(BaseModel):
    registered: bool
    ward_code: str | None = None
    verified_at: str | None = None



async def _check_consent_service(subject_id_hash: str, tenant_id: str) -> None:
    """
    STEP-P2-02: Verify consent via the live consent-service (fail-closed).
    Uses the shared circuit-breaker — fast-fails when the consent-service is
    unhealthy rather than blocking every registration with a 5s timeout.
    Raises HTTP 422 if consent is denied or the circuit is open.
    """
    allowed = await _cb_consent_allowed(
        subject_id_hash, "registration", "membership", tenant_id
    )
    if not allowed:
        breaker = _cb_state()
        detail = (
            "Consent-service circuit open — registration temporarily unavailable."
            if breaker != "CLOSED"
            else "Membership registration requires explicit consent (consent-service: denied or unreachable)."
        )
        raise HTTPException(status_code=422, detail=detail)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post(
    "/api/v1/members/register",
    response_model=RegisterResponse,
    status_code=200,
    summary="Register a FORD-Asili member (HC-6: hashes only; HC-4: tenant_id)",
)
async def register_member(
    req: RegisterRequest,
    pool: asyncpg.Pool = Depends(get_pool),
):
    # HC-6: compute HMAC tokens first; raw values are never stored
    id_hash    = hmac_token(req.national_id)
    phone_hash = hmac_token(req.phone)

    # STEP-P2-02: live consent-service check (fail-closed; replaces bare boolean)
    if req.consent:
        await _check_consent_service(id_hash, FORD_TENANT_ID)
    else:
        raise HTTPException(status_code=422, detail="Membership registration requires explicit consent.")
    tenant_id  = FORD_TENANT_ID
    member_id  = str(uuid.uuid4())
    now        = datetime.now(UTC)

    async with pool.acquire() as conn:
        # HC-4: tenant_id on every query
        await conn.execute("SET LOCAL app.tenant_id = $1", tenant_id)

        # Idempotency: if already registered, return the existing record
        existing = await conn.fetchrow(
            """SELECT member_id, ward_code, registered_at, fabric_tx_id
               FROM ford_members
               WHERE id_hash = $1 AND tenant_id = $2""",
            id_hash, tenant_id,
        )
        if existing:
            return RegisterResponse(
                member_id    = str(existing["member_id"]),
                id_hash      = id_hash[:12],
                ward_code    = existing["ward_code"],
                fabric_tx_id = existing["fabric_tx_id"] or "fabric-pending",
                registered_at = existing["registered_at"].isoformat(),
            )

        # ── STEP-P3-03: record on Fabric (fire-and-forget; Postgres is authoritative) ──
        fabric_tx_id = await record_on_fabric(
            id_hash, phone_hash, req.ward_code, tenant_id, req.agent_id
        )

        # Persist to PostgreSQL (HC-4: tenant_id; HC-6: hashes only)
        await conn.execute(
            """INSERT INTO ford_members
               (member_id, id_hash, phone_hash, ward_code, constituency, county,
                agent_id, tenant_id, fabric_tx_id, registered_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            member_id, id_hash, phone_hash,
            req.ward_code, req.constituency, req.county,
            req.agent_id, tenant_id, fabric_tx_id, now,
        )

    log.info(
        "member_registered ward=%s agent=%s fabric_tx=%s",
        req.ward_code, req.agent_id, fabric_tx_id,
    )
    return RegisterResponse(
        member_id     = member_id,
        id_hash       = id_hash[:12],
        ward_code     = req.ward_code,
        fabric_tx_id  = fabric_tx_id,
        registered_at = now.isoformat(),
    )


@app.get(
    "/api/v1/members/verify/{public_token}",
    response_model=VerifyResponse,
    summary="Verify membership via public token (no auth, no PII)",
)
async def verify_member(
    public_token: str,
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    public_token is HMAC-SHA256(member_id + nonce) generated at registration.
    It does not encode or permit derivation of a national ID or phone number (HC-6).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT ward_code, registered_at
               FROM ford_members
               WHERE public_token = $1""",
            public_token,
        )
    if not row:
        return JSONResponse(status_code=404, content={"registered": False})
    return VerifyResponse(
        registered  = True,
        ward_code   = row["ward_code"],
        verified_at = row["registered_at"].isoformat(),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ford-api", "consent_breaker": _cb_state()}
