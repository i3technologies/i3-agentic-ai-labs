#!/usr/bin/env python3
"""
i3 SIT Digital Work-Centers API — FastAPI
Endpoints: enrollment, exam booking, credentials, ecitizen, membership, professionals
"""
import hashlib
import io
import os
import uuid
import logging
import httpx
import asyncpg
import boto3
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File

# Circuit-breaker for the consent-service (fail-closed, STEP-P2-02)
from platform.consent.circuit_breaker import consent_allowed as _cb_consent_allowed, breaker_state as _cb_state
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

log = logging.getLogger("sit-api")
logging.basicConfig(level=logging.INFO)

DATABASE_URL          = os.environ["DATABASE_URL"]
LITELLM_URL           = os.environ.get("LITELLM_URL", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY           = os.environ.get("LITELLM_KEY", "")
EVALOS_URL            = os.environ.get("EVALOS_URL", "http://evalos-web.i3-evalos.svc.cluster.local:3000")
TALENT_API_URL        = os.environ.get("TALENT_API_URL", "http://talent-api.i3-talent.svc.cluster.local:8000")
SEAWEEDFS_URL         = os.environ.get("SEAWEEDFS_S3_URL", "http://seaweedfs-s3.i3-ott.svc.cluster.local:8333")
CREDENTIAL_SERVICE_URL = os.environ.get(
    "CREDENTIAL_SERVICE_URL",
    "http://credential-service.i3-evalos.svc.cluster.local:8000",
)
# STEP-P2-02: live consent service (replaces bare boolean field)
CONSENT_SERVICE_URL   = os.environ.get(
    "CONSENT_SERVICE_URL",
    "http://consent-service.i3-consent.svc.cluster.local:8000",
)
SIT_TENANT_ID         = os.environ.get("SIT_TENANT_ID", "00000000-0000-0000-0000-000000000004")

from fastapi.responses import RedirectResponse

# ── Pool lifecycle ─────────────────────────────────────────────────────────────
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
    log.info("asyncpg pool ready (min=2 max=10)")
    yield
    await _pool.close()
    log.info("sit-api shutdown: pool closed")


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "pool not initialised"
    return _pool


app = FastAPI(title="i3 SIT API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sit.i3technologies.co.ke",
        "https://evalos.i3technologies.co.ke",
        "https://engage.i3technologies.co.ke",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


# ── Models ────────────────────────────────────────────────────────────────────
class LearnerCreate(BaseModel):
    keycloak_sub: str
    full_name: str
    id_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    ward: Optional[str] = None
    consent: bool = False

class EnrollmentCreate(BaseModel):
    learner_id: str
    course_id: str

class ExamBooking(BaseModel):
    enrollment_id: str

class CredentialIssue(BaseModel):
    learner_id: str
    course_id: str
    cert_content: str  # Base64-encoded cert text for hashing
    tenant_id: Optional[str] = None  # HC-4: forwarded to credential-service

class EcitizenCase(BaseModel):
    citizen_id: str
    service: str  # KRA | NSSF | SHA | NTSA | ArdhiSasa

class MembershipCreate(BaseModel):
    learner_id: str
    tier: str  # daily | monthly | student | corporate

class ProfBooking(BaseModel):
    client_id: str
    professional_id: str
    service_type: str
    scheduled_at: str


# ── Learners ──────────────────────────────────────────────────────────────────
async def _check_sit_consent(subject_hash: str, tenant_id: str) -> None:
    """
    STEP-P2-02: Verify learner consent via the live consent-service (fail-closed).
    Uses the shared circuit-breaker — fast-fails when consent-service is unhealthy.
    """
    allowed = await _cb_consent_allowed(subject_hash, "enrollment", "education", tenant_id)
    if not allowed:
        breaker = _cb_state()
        detail = (
            "Consent-service circuit open — enrollment temporarily unavailable."
            if breaker != "CLOSED"
            else "Consent is required under Data Protection Act 2019 (consent-service: denied or unreachable)."
        )
        raise HTTPException(400, detail)


@app.post("/api/v1/learners", status_code=201)
async def create_learner(req: LearnerCreate):
    # Derive subject hash for consent lookup (use keycloak_sub as the identifier)
    subject_hash = hashlib.sha256(req.keycloak_sub.encode()).hexdigest()  # public sub; not PII
    if req.consent:
        await _check_sit_consent(subject_hash, SIT_TENANT_ID)
    else:
        raise HTTPException(400, "Consent is required under Data Protection Act 2019")
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO learners (keycloak_sub, full_name, id_number, phone, email, ward, consent_at)
            VALUES ($1,$2,$3,$4,$5,$6, now())
            ON CONFLICT (keycloak_sub) DO UPDATE SET full_name = EXCLUDED.full_name
            RETURNING id, keycloak_sub, full_name, created_at
        """, req.keycloak_sub, req.full_name, req.id_number, req.phone, req.email, req.ward)
    return dict(row)


# ── Enrollment ────────────────────────────────────────────────────────────────
@app.post("/api/v1/enrollments", status_code=201)
async def create_enrollment(req: EnrollmentCreate):
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO enrollments (learner_id, course_id)
            VALUES ($1, $2) RETURNING id, learner_id, course_id, enrolled_at, status
        """, uuid.UUID(req.learner_id), uuid.UUID(req.course_id))
    return dict(row)


# ── Exam booking (EvalOS bridge) ──────────────────────────────────────────────
@app.post("/api/v1/exam-bookings", status_code=201)
async def book_exam(req: ExamBooking):
    async with get_pool().acquire() as conn:
        enroll = await conn.fetchrow("SELECT * FROM enrollments WHERE id = $1", uuid.UUID(req.enrollment_id))
        if not enroll:
            raise HTTPException(404, "Enrollment not found")
        # Trigger EvalOS session creation
        evalos_session_id = f"sit-{uuid.uuid4().hex[:12]}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(f"{EVALOS_URL}/api/sessions", json={
                    "external_id": evalos_session_id,
                    "source": "sit",
                    "enrollment_id": req.enrollment_id
                })
                if r.status_code in (200, 201):
                    evalos_session_id = r.json().get("session_id", evalos_session_id)
        except Exception as e:
            log.warning(f"EvalOS session creation failed: {e} — using local ID")

        row = await conn.fetchrow("""
            INSERT INTO exam_bookings (enrollment_id, evalos_session_id, status)
            VALUES ($1, $2, 'scheduled') RETURNING *
        """, uuid.UUID(req.enrollment_id), evalos_session_id)
    return dict(row)


# ── Credential issuance (delegates to credential-service) ────────────────────
@app.post("/api/v1/credentials", status_code=201)
async def issue_credential(req: CredentialIssue):
    """
    Delegate W3C VC 2.0 issuance to credential-service, then bridge to
    Talent Cloud using learner/course metadata fetched locally.
    HC-4: tenant_id is forwarded; falls back to a per-learner lookup.
    """
    async with get_pool().acquire() as conn:
        learner = await conn.fetchrow("SELECT * FROM learners WHERE id = $1", uuid.UUID(req.learner_id))
        course  = await conn.fetchrow("SELECT * FROM courses WHERE id = $1", uuid.UUID(req.course_id))

    if not learner or not course:
        raise HTTPException(404, "Learner or course not found")

    tenant_id = req.tenant_id or str(learner.get("tenant_id", uuid.UUID(int=0)))

    # Call credential-service
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.post(
            f"{CREDENTIAL_SERVICE_URL}/credentials",
            json={
                "holder_id": req.learner_id,
                "holder_name": learner["full_name"],
                "credential_type": "course_completion",
                "issuer": "did:i3:sit-platform",
                "evidence": {},
                "tenant_id": tenant_id,
            },
        )
        if resp.status_code not in (200, 201):
            raise HTTPException(502, f"Credential service error: {resp.status_code}")
        vc_payload = resp.json()

    qr_token      = vc_payload["qr_token"]
    credential_id = vc_payload["credential_id"]

    # Bridge to Talent Cloud — best-effort
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            tc = await client.post(f"{TALENT_API_URL}/api/v1/candidates", json={
                "keycloak_sub": learner["keycloak_sub"],
                "full_name": learner["full_name"],
                "email": learner.get("email"),
                "source": "sit",
                "evalos_passport_id": None,
            })
            if tc.status_code in (200, 201):
                log.info(f"Talent Cloud candidate created: {tc.json().get('id')}")
    except Exception as e:
        log.warning(f"Talent Cloud bridge failed: {e}")

    return {
        "id": credential_id,
        "qr_token": qr_token,
        "vc_json": vc_payload.get("vc_json"),
        "verify_url": f"https://verify.sit.i3technologies.co.ke/{qr_token}",
    }


@app.get("/api/v1/credentials/verify/{qr_token}")
async def verify_credential(qr_token: str):
    """Public QR verification — proxied to credential-service."""
    async with httpx.AsyncClient(timeout=8) as client:
        resp = await client.get(
            f"{CREDENTIAL_SERVICE_URL}/credentials/{qr_token}/verify"
        )
    if resp.status_code == 404:
        raise HTTPException(404, "Credential not found or QR token invalid")
    if not resp.is_success:
        raise HTTPException(502, "Credential service error")
    return resp.json()


# ── eCitizen cases ────────────────────────────────────────────────────────────
@app.post("/api/v1/ecitizen", status_code=201)
async def create_ecitizen_case(req: EcitizenCase):
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO ecitizen_cases (citizen_id, service, status)
            VALUES ($1, $2, 'open') RETURNING id, citizen_id, service, status, created_at
        """, uuid.UUID(req.citizen_id), req.service)
    # Trigger n8n workflow (best-effort, outside connection)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post("http://n8n.i3-ott.svc:5678/webhook/ecitizen-case", json={
                "case_id": str(row["id"]), "service": req.service, "citizen_id": req.citizen_id
            })
    except Exception as e:
        log.warning(f"n8n trigger failed: {e}")
    return dict(row)


# ── Memberships ───────────────────────────────────────────────────────────────
@app.post("/api/v1/memberships", status_code=201)
async def create_membership(req: MembershipCreate):
    from datetime import timedelta
    qr_token = str(uuid.uuid4())
    durations = {"daily": 1, "monthly": 30, "student": 180, "corporate": 365}
    days = durations.get(req.tier, 30)
    now = datetime.now(timezone.utc)
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO membership_subscriptions (learner_id, tier, starts_at, expires_at, qr_token)
            VALUES ($1, $2, $3, $4, $5) RETURNING id, tier, starts_at, expires_at, qr_token
        """, uuid.UUID(req.learner_id), req.tier, now, now + timedelta(days=days), qr_token)
    return dict(row)


# ── Professional bookings ─────────────────────────────────────────────────────
@app.post("/api/v1/professional-bookings", status_code=201)
async def book_professional(req: ProfBooking):
    room_id = f"webrtc-{uuid.uuid4().hex[:8]}"
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO professional_bookings
              (client_id, professional_id, service_type, scheduled_at, webrtc_room_id)
            VALUES ($1,$2,$3,$4::timestamptz,$5) RETURNING id, status, webrtc_room_id
        """, uuid.UUID(req.client_id), req.professional_id, req.service_type,
             req.scheduled_at, room_id)
    return dict(row)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "sit-api", "version": "1.0.0", "consent_breaker": _cb_state()}
