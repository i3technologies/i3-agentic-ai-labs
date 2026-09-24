"""
Credential Service — data models placeholder.
In-memory store used for development; swap for asyncpg pool in production.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class CredentialRecord:
    credential_id: uuid.UUID
    holder_id: uuid.UUID
    holder_name: str
    credential_type: str
    issuer: str
    tenant_id: uuid.UUID
    qr_token: str
    vc_json: Dict[str, Any]
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
