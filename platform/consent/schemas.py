"""
Pydantic request/response schemas for the consent-service HTTP API.
Validates all inbound payloads and serialises outbound responses.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime
import uuid


# ── Request schemas ────────────────────────────────────────────────────────────

class ConsentCreate(BaseModel):
    """POST /consent — record a new consent decision."""
    subject_id_hash: str = Field(..., min_length=64, max_length=64,
                                  description="HMAC-SHA256 hex digest of subject's national_id or email")
    channel: Literal["email", "sms", "whatsapp", "voice"]
    purpose: Literal["marketing", "otp", "enrollment", "survey"]
    status: Literal["granted", "revoked"]
    source: str = Field(..., max_length=100,
                         description="registration_form | api | ussd")
    expiry: Optional[datetime] = None
    version: int = Field(default=1, ge=1)
    tenant_id: uuid.UUID


class ConsentErasureRequest(BaseModel):
    """DELETE /consent/{subject_id_hash} — request right-to-erasure."""
    reason: str = Field(..., max_length=500)
    requested_by: str = Field(..., max_length=200)
    tenant_id: uuid.UUID


# ── Response schemas ───────────────────────────────────────────────────────────

class ConsentCreatedResponse(BaseModel):
    """201 response for POST /consent."""
    consent_id: uuid.UUID
    recorded_at: datetime


class ConsentCheckResponse(BaseModel):
    """200 response for GET /consent/{subject_id_hash}."""
    allowed: bool
    recorded_at: Optional[datetime] = None
    expiry: Optional[datetime] = None


class ConsentErasureResponse(BaseModel):
    """200 response for DELETE /consent/{subject_id_hash}."""
    erasure_job_id: uuid.UUID
    status: Literal["queued"]


class ConsentAuditEventSchema(BaseModel):
    """Single audit event in the GET /consent/{subject_id_hash}/audit response."""
    id: uuid.UUID
    consent_id: Optional[uuid.UUID]
    tenant_id: uuid.UUID
    event_type: str
    actor: Optional[str]
    timestamp: datetime
    metadata: Optional[dict]


class ConsentAuditResponse(BaseModel):
    """200 response for GET /consent/{subject_id_hash}/audit."""
    events: list[ConsentAuditEventSchema]
