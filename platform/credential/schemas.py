"""
Credential Service — Pydantic schemas (request / response)
W3C Verifiable Credentials 2.0 — JSON-LD envelope
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ── Request ────────────────────────────────────────────────────────────────────

class CredentialEvidence(BaseModel):
    exam_id: Optional[uuid.UUID] = None
    score: Optional[int] = None
    passed: Optional[bool] = None


CredentialType = Literal["course_completion", "exam_pass", "membership"]


class CredentialIssueRequest(BaseModel):
    holder_id: uuid.UUID
    holder_name: str
    credential_type: CredentialType
    issuer: str
    evidence: CredentialEvidence = Field(default_factory=CredentialEvidence)
    tenant_id: uuid.UUID


# ── W3C VC 2.0 JSON-LD structures ─────────────────────────────────────────────

class CredentialSubject(BaseModel):
    id: str  # "did:i3:<holder_id>"
    holder_name: str
    credential_type: str
    evidence: Dict[str, Any]


class W3CVerifiableCredential(BaseModel):
    context: List[str] = Field(
        default=[
            "https://www.w3.org/2018/credentials/v1",
            "https://www.w3.org/2018/credentials/v2",
        ],
        alias="@context",
    )
    id: str  # "urn:uuid:<credential_id>"
    type: List[str]
    issuer: str
    issuanceDate: str  # ISO8601
    credentialSubject: CredentialSubject

    model_config = {"populate_by_name": True}


# ── Response ───────────────────────────────────────────────────────────────────

class CredentialIssueResponse(BaseModel):
    credential_id: uuid.UUID
    qr_token: str
    vc_json: Dict[str, Any]


class CredentialVerifyResponse(BaseModel):
    valid: bool
    holder_name: Optional[str] = None
    credential_type: Optional[str] = None
    issued_at: Optional[str] = None
