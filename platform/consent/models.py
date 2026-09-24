"""
SQLAlchemy-free domain models for the consent-service.
All persistence is done via raw asyncpg SQL queries (see main.py).
This module defines Python dataclasses used as internal domain objects.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class ConsentRecord:
    id: uuid.UUID
    tenant_id: uuid.UUID
    subject_id_hash: str          # HMAC-SHA256 of national_id or email
    channel: str                  # email | sms | whatsapp | voice
    purpose: str                  # marketing | otp | enrollment | survey
    status: str                   # granted | revoked | expired
    recorded_at: datetime
    source: Optional[str] = None  # registration_form | api | ussd
    expiry: Optional[datetime] = None
    version: int = 1


@dataclass
class ConsentAuditEvent:
    id: uuid.UUID
    consent_id: Optional[uuid.UUID]
    tenant_id: uuid.UUID
    event_type: str               # granted | revoked | checked | erased
    timestamp: datetime
    actor: Optional[str] = None
    metadata: Optional[dict] = field(default=None)
