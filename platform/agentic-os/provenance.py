"""
i3 Agentic AI OS — Provenance Hashing Utility
File: platform/agentic-os/provenance.py

Shared by agent_runtime.py and trace_flywheel.py so that neither module
creates an import dependency on the other.

HC-6: All provenance hashes must use keyed HMAC-SHA256 (MEMBER_HMAC_SECRET
      from OpenBao).  Raw SHA-256 is forbidden for any identifier that may
      trace back to a Kenyan National ID or phone number.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

log = logging.getLogger("agentic-os.provenance")

# Injected at pod startup from OpenBao secret i3/member-hmac-secret (HC-6)
_MEMBER_HMAC_SECRET = os.environ.get("MEMBER_HMAC_SECRET", "")


def provenance_hash(trace_id: str) -> str:
    """
    Return HMAC-SHA256(trace_id, MEMBER_HMAC_SECRET).

    Falls back to a 64-character zero string when the secret is not set,
    logging a WARNING so the absence is observable in logs without crashing
    the pipeline.
    """
    secret = os.environ.get("MEMBER_HMAC_SECRET", _MEMBER_HMAC_SECRET)
    if not secret:
        log.warning("MEMBER_HMAC_SECRET not set — provenance hash will be zeroed (HC-6)")
        return "0" * 64
    return hmac.new(
        secret.encode(),
        trace_id.encode(),
        hashlib.sha256,
    ).hexdigest()
