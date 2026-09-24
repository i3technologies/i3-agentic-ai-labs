"""
platform/audit/models.py — WORM audit event model (IMP-09)

AuditEvent is the canonical structured record written to append-only object
storage.  Every field maps directly to the audit schema fields required by
IMP-09:  who / what / when / tenant / risk-tier / outcome.

A chained HMAC field (prev_hash + payload HMAC) provides tamper evidence
across the ordered log sequence for a given tenant partition.

HC-4 compliance: tenant_id is required (UUID, NOT NULL).
HC-6 compliance: actor_id is the HMAC-SHA256 of the originating user/service
                 identifier — never the raw NID or email address.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RiskTier(str, Enum):
    """Risk classification for the operation being audited."""
    LOW       = "LOW"
    MEDIUM    = "MEDIUM"
    HIGH      = "HIGH"
    CRITICAL  = "CRITICAL"


class Outcome(str, Enum):
    """End-state of the audited operation."""
    SUCCESS    = "SUCCESS"
    FAILURE    = "FAILURE"
    DENIED     = "DENIED"
    PARTIAL    = "PARTIAL"
    UNKNOWN    = "UNKNOWN"


# ---------------------------------------------------------------------------
# Core event model
# ---------------------------------------------------------------------------

class AuditEvent(BaseModel):
    """
    Structured audit event.

    Serialised as newline-delimited JSON (NDJSON) and written to
    append-only object storage.  The `event_hmac` field covers the
    canonical payload (all fields except `event_hmac` itself) so that
    any post-write mutation is detectable.

    Fields
    ------
    event_id        — UUIDv4, unique per event.
    occurred_at     — ISO-8601 UTC timestamp of the audited action.
    tenant_id       — UUID of the owning tenant (HC-4: never NULL).
    tenant_slug     — Human-readable tenant slug for query / display.
    actor_id        — HMAC-SHA256 hex of actor NID / email (HC-6).
    actor_role      — Role of the actor (e.g. "admin", "agent:admissions").
    service         — Originating service name (e.g. "evalos", "admissions").
    action          — Verb describing the operation (e.g. "exam.submit").
    resource_type   — Kind of the resource affected (e.g. "Exam", "Ballot").
    resource_id     — Identifier of the resource (opaque string).
    risk_tier       — RiskTier enum: LOW / MEDIUM / HIGH / CRITICAL.
    outcome         — Outcome enum: SUCCESS / FAILURE / DENIED / PARTIAL / UNKNOWN.
    detail          — Free-form JSON-serialisable context dict (optional).
    prev_hash       — HMAC of the immediately preceding event in the same
                      tenant partition ("GENESIS" for the first event).
    event_hmac      — HMAC-SHA256 of the canonical payload of *this* event.
                      Computed by AuditEvent.sign(secret).
    """

    # Identity
    event_id:      uuid.UUID = Field(default_factory=uuid.uuid4)
    occurred_at:   datetime  = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    # Tenancy (HC-4)
    tenant_id:   uuid.UUID = Field(..., description="Owning tenant UUID (HC-4: NOT NULL)")
    tenant_slug: str       = Field(..., min_length=1, max_length=64)

    # Actor (HC-6 — HMAC of real identifier, never raw NID)
    actor_id:   str = Field(..., min_length=64, max_length=64,
                             description="HMAC-SHA256 hex of actor identifier (HC-6)")
    actor_role: str = Field(..., max_length=128)

    # Operation
    service:       str = Field(..., max_length=64)
    action:        str = Field(..., max_length=128)
    resource_type: str = Field(..., max_length=64)
    resource_id:   str = Field(..., max_length=256)

    # Classification
    risk_tier: RiskTier
    outcome:   Outcome

    # Optional structured context
    detail: Optional[dict[str, Any]] = None

    # Tamper-evidence chain
    prev_hash:  str = Field(default="GENESIS", max_length=64)
    event_hmac: str = Field(default="", max_length=64)

    @field_validator("actor_id")
    @classmethod
    def actor_id_must_be_hmac_hex(cls, v: str) -> str:
        """Reject any actor_id that is not a 64-char lowercase hex string (HC-6)."""
        if not all(c in "0123456789abcdef" for c in v.lower()) or len(v) != 64:
            raise ValueError(
                "actor_id must be a 64-char HMAC-SHA256 hex digest (HC-6). "
                "Never pass a raw NID or email address."
            )
        return v.lower()

    # ------------------------------------------------------------------
    # Tamper-evidence helpers
    # ------------------------------------------------------------------

    def canonical_payload(self) -> bytes:
        """
        Deterministic JSON bytes used for HMAC computation.

        Fields: all *except* event_hmac, sorted by key.
        occurred_at is serialised as ISO-8601 UTC without microseconds to
        ensure stable bytes across Python versions.
        """
        data: dict[str, Any] = {
            "event_id":      str(self.event_id),
            "occurred_at":   self.occurred_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tenant_id":     str(self.tenant_id),
            "tenant_slug":   self.tenant_slug,
            "actor_id":      self.actor_id,
            "actor_role":    self.actor_role,
            "service":       self.service,
            "action":        self.action,
            "resource_type": self.resource_type,
            "resource_id":   self.resource_id,
            "risk_tier":     self.risk_tier.value,
            "outcome":       self.outcome.value,
            "detail":        self.detail,
            "prev_hash":     self.prev_hash,
        }
        return json.dumps(data, sort_keys=True, ensure_ascii=False).encode()

    def sign(self, secret: bytes) -> "AuditEvent":
        """
        Compute and set event_hmac.  Returns *self* (mutates in-place).

        secret must be the keyed HMAC secret from OpenBao
        (i3/audit/hmac-secret) — not a raw SHA-256 digest (HC-6).
        """
        mac = hmac.new(secret, self.canonical_payload(), hashlib.sha256)
        self.event_hmac = mac.hexdigest()
        return self

    def verify(self, secret: bytes) -> bool:
        """
        Return True iff the stored event_hmac matches a freshly computed one.
        Uses hmac.compare_digest to prevent timing attacks.
        """
        mac = hmac.new(secret, self.canonical_payload(), hashlib.sha256)
        expected = mac.hexdigest()
        return hmac.compare_digest(expected.encode(), self.event_hmac.encode())
