#!/usr/bin/env python3
"""
Credential Service
------------------
FastAPI microservice for W3C Verifiable Credentials 2.0 issuance
and public QR-token verification.

Deployed in: i3-evalos namespace
Cluster-internal DNS: credential-service.i3-evalos.svc.cluster.local:8000

HC-4: tenant_id is required on every issuance request.
HC-6: holder_id is stored as-is (UUID); no raw National ID/phone persisted here.

QR tokens are short-lived signed JWTs (HS256, 24-hour TTL) bound to the
credential_id so they can be re-verified without a database round-trip.
The store below is an asyncpg pool (cluster) or an in-memory dict (dev/test).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from schemas import (
    CredentialIssueRequest,
    CredentialIssueResponse,
    CredentialVerifyResponse,
    CredentialSubject,
    W3CVerifiableCredential,
)
from models import CredentialRecord

log = logging.getLogger("credential-service")
logging.basicConfig(level=logging.INFO)

DATABASE_URL: Optional[str] = os.environ.get("DATABASE_URL")
QR_SECRET: str = os.environ.get("CREDENTIAL_QR_SECRET", "change-me-in-production")
QR_TTL_SECONDS: int = int(os.environ.get("CREDENTIAL_QR_TTL", str(24 * 3600)))
ISSUER_DID: str = os.environ.get("CREDENTIAL_ISSUER_DID", "did:i3:platform")

# ── Pool (production) / in-memory fallback (dev) ──────────────────────────────
_pool: Optional[asyncpg.Pool] = None
_dev_store: Dict[str, CredentialRecord] = {}  # qr_token -> record (dev only)


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _pool
    if DATABASE_URL:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            statement_cache_size=0,
        )
        log.info("asyncpg pool created")
    else:
        log.warning("DATABASE_URL not set — using in-memory store (dev mode only)")
    yield
    if _pool:
        await _pool.close()


app = FastAPI(title="i3 Credential Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://evalos.i3technologies.co.ke",
        "https://engage.i3technologies.co.ke",
    ],
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)


# ── QR token helpers ──────────────────────────────────────────────────────────

def _sign_qr_token(credential_id: str) -> str:
    """
    Produce a short-lived HMAC-SHA256 signed token:
    base64url(payload_json) + "." + hex(hmac)
    """
    payload = json.dumps(
        {"cid": credential_id, "exp": int(time.time()) + QR_TTL_SECONDS},
        separators=(",", ":"),
    ).encode()
    import base64
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    sig = hmac.new(QR_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def _verify_qr_token(token: str) -> Optional[str]:
    """Return credential_id if token is valid and unexpired, else None."""
    import base64
    try:
        b64, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(QR_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        padding = "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(b64 + padding))
    except Exception:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload.get("cid")


# ── W3C VC 2.0 builder ────────────────────────────────────────────────────────

_CREDENTIAL_TYPE_LABELS: Dict[str, str] = {
    "course_completion": "CourseCompletionCredential",
    "exam_pass": "ExamPassCredential",
    "membership": "MembershipCredential",
}


def _build_vc(
    credential_id: uuid.UUID,
    req: CredentialIssueRequest,
    issued_at: datetime,
) -> Dict[str, Any]:
    vc_type = _CREDENTIAL_TYPE_LABELS.get(req.credential_type, "VerifiableCredential")
    subject = CredentialSubject(
        id=f"did:i3:{req.holder_id}",
        holder_name=req.holder_name,
        credential_type=req.credential_type,
        evidence=req.evidence.model_dump(exclude_none=True),
    )
    vc = W3CVerifiableCredential(
        **{
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://www.w3.org/2018/credentials/v2",
            ],
            "id": f"urn:uuid:{credential_id}",
            "type": ["VerifiableCredential", vc_type],
            "issuer": req.issuer or ISSUER_DID,
            "issuanceDate": issued_at.isoformat(),
            "credentialSubject": subject,
        }
    )
    return vc.model_dump(by_alias=True)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _persist(record: CredentialRecord) -> None:
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO credentials_vc
                  (id, holder_id, holder_name, credential_type, issuer,
                   tenant_id, qr_token, vc_json, issued_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO NOTHING
                """,
                record.credential_id,
                record.holder_id,
                record.holder_name,
                record.credential_type,
                record.issuer,
                record.tenant_id,
                record.qr_token,
                json.dumps(record.vc_json),
                record.issued_at,
            )
    else:
        _dev_store[record.qr_token] = record


async def _lookup_by_qr(qr_token: str) -> Optional[CredentialRecord]:
    if _pool:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, holder_id, holder_name, credential_type, issuer,
                       tenant_id, qr_token, vc_json, issued_at
                FROM credentials_vc WHERE qr_token = $1
                """,
                qr_token,
            )
        if not row:
            return None
        return CredentialRecord(
            credential_id=row["id"],
            holder_id=row["holder_id"],
            holder_name=row["holder_name"],
            credential_type=row["credential_type"],
            issuer=row["issuer"],
            tenant_id=row["tenant_id"],
            qr_token=row["qr_token"],
            vc_json=json.loads(row["vc_json"]) if isinstance(row["vc_json"], str) else row["vc_json"],
            issued_at=row["issued_at"],
        )
    return _dev_store.get(qr_token)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/credentials", response_model=CredentialIssueResponse, status_code=201)
async def issue_credential(req: CredentialIssueRequest) -> CredentialIssueResponse:
    """
    Issue a W3C VC 2.0 credential.
    HC-4: tenant_id required (enforced by Pydantic schema — non-nullable UUID).
    """
    credential_id = uuid.uuid4()
    issued_at = datetime.now(timezone.utc)
    qr_token = _sign_qr_token(str(credential_id))
    vc_json = _build_vc(credential_id, req, issued_at)

    record = CredentialRecord(
        credential_id=credential_id,
        holder_id=req.holder_id,
        holder_name=req.holder_name,
        credential_type=req.credential_type,
        issuer=req.issuer or ISSUER_DID,
        tenant_id=req.tenant_id,
        qr_token=qr_token,
        vc_json=vc_json,
        issued_at=issued_at,
    )
    await _persist(record)

    return CredentialIssueResponse(
        credential_id=credential_id,
        qr_token=qr_token,
        vc_json=vc_json,
    )


@app.get("/credentials/{qr_token}/verify", response_model=CredentialVerifyResponse)
async def verify_credential(qr_token: str) -> CredentialVerifyResponse:
    """
    Public endpoint — no authentication required.
    Verifies QR token signature + expiry, then returns credential metadata.
    """
    credential_id = _verify_qr_token(qr_token)
    if not credential_id:
        raise HTTPException(status_code=404, detail={"valid": False})

    record = await _lookup_by_qr(qr_token)
    if not record:
        raise HTTPException(status_code=404, detail={"valid": False})

    return CredentialVerifyResponse(
        valid=True,
        holder_name=record.holder_name,
        credential_type=record.credential_type,
        issued_at=record.issued_at.isoformat(),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "credential-service", "version": "1.0.0"}
