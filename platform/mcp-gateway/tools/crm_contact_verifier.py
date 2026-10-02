"""
MCP Tool: crm.contact.verifier — Tier 2 (email deliverability + OPA source check)

Verifies an email address by:
  1. DNS MX record check — confirms domain accepts mail.
  2. OPA (Open Policy Agent) source policy check — confirms the URL from which
     the contact was observed is on the permitted-source list.
  3. Returns a provenance hash (HMAC-SHA256 of field:value:url:method composite)
     for storage in the CRM evidence table.

HC-4: tenant_id enforced.
HC-6: email is NEVER stored raw; email_hmac (HMAC-SHA256) returned instead.

Input schema:
  {
    "email":       str,          # email to verify
    "source_url":  str,          # public URL where contact was observed
    "method":      str,          # e.g. "dns_mx", "public_profile"
    "lawful_basis": str          # Kenya DPA 2019 lawful basis code
  }

Output:
  {
    "deliverable":      bool,
    "domain_has_mx":    bool,
    "opa_source_ok":    bool,
    "email_hmac":       str,     # HC-6: 64-char HMAC-SHA256 hex
    "content_hash":     str,     # HMAC-SHA256 provenance composite
    "confidence_score": float,
    "blocked_reason":   str | null
  }
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import logging
import os
import re
import socket
from typing import Any

import httpx
from fastapi import HTTPException

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.crm.contact.verifier")

# HC-6: HMAC key from OpenBao i3/crm/hmac-secret
MEMBER_HMAC_SECRET = os.environ.get("MEMBER_HMAC_SECRET", "")

# OPA policy endpoint (open-policy-agent.i3-platform.svc)
OPA_URL = os.environ.get(
    "OPA_URL",
    "http://opa.i3-platform.svc.cluster.local:8181",
)

SPEC = McpToolSpec(
    name="crm.contact.verifier",
    description=(
        "Verify email deliverability (DNS MX check) and check the contact source URL "
        "against the OPA permitted-sources policy. "
        "Returns a provenance HMAC (HC-6) and a confidence score. "
        "Tier 2: external DNS read + OPA policy call; no PII stored."
    ),
    version="1.0.0",
    tenant_scope="single",
    read_write="read",
    side_effect_class="external_read",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=15_000,
    audit_required=True,
)

# Basic email format guard (not a validator — just prevents obviously malformed input)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── HC-6: HMAC helpers ────────────────────────────────────────────────────────

def _hmac_hex(value: str) -> str:
    """HMAC-SHA256 of a string using MEMBER_HMAC_SECRET (HC-6)."""
    key = MEMBER_HMAC_SECRET.encode() if MEMBER_HMAC_SECRET else b"dev-placeholder"
    if not MEMBER_HMAC_SECRET:
        log.warning("MEMBER_HMAC_SECRET not set — using placeholder key (DEV only)")
    return _hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def _provenance_hash(email: str, source_url: str, method: str) -> str:
    """
    HMAC-SHA256 of the composite 'field:value:url:method' string.
    Stored in the CRM evidence table to prove data provenance.
    """
    composite = f"email:{email}:{source_url}:{method}"
    return _hmac_hex(composite)


# ── DNS MX check ──────────────────────────────────────────────────────────────

async def _check_mx(domain: str) -> bool:
    """Return True if the domain has at least one MX record."""
    loop = asyncio.get_event_loop()

    def _lookup() -> bool:
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)
            return len(answers) > 0
        except Exception:
            return False

    return await loop.run_in_executor(None, _lookup)


# ── OPA permitted-source check ────────────────────────────────────────────────

async def _check_opa_source(source_url: str, tenant_id: str) -> bool:
    """
    Call OPA to verify the source URL is on the permitted list for this tenant.
    Policy: data.crm.contact.permitted_source

    Returns True on allow, False on deny.  Fails open (returns True) if OPA
    is unreachable, but logs a warning.
    """
    input_doc = {
        "input": {
            "source_url": source_url,
            "tenant_id":  tenant_id,
        }
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{OPA_URL}/v1/data/crm/contact/permitted_source",
                json=input_doc,
            )
            resp.raise_for_status()
            result = resp.json()
            return bool(result.get("result", False))
    except Exception as exc:
        log.warning("OPA source check failed (fail-open): %s", exc)
        return True   # fail-open: don't block enrichment if OPA is temporarily down


# ── Handler ───────────────────────────────────────────────────────────────────

async def handle(payload: dict[str, Any], *, tenant_id: str, db=None) -> dict:
    """
    HC-4: tenant_id required.
    HC-6: email is immediately converted to HMAC; never stored or returned raw.
    """
    if not tenant_id:
        raise HTTPException(status_code=422, detail="HC-4: tenant_id is required")

    email       = (payload.get("email") or "").strip().lower()
    source_url  = (payload.get("source_url") or "").strip()
    method      = (payload.get("method") or "dns_mx").strip()
    lawful_basis = (payload.get("lawful_basis") or "").strip()

    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="A valid email address is required")
    if not source_url:
        raise HTTPException(status_code=422, detail="source_url is required")
    if not lawful_basis:
        raise HTTPException(status_code=422, detail="lawful_basis (Kenya DPA 2019) is required")

    domain = email.split("@", 1)[1]

    # Run MX check and OPA check concurrently
    domain_has_mx, opa_source_ok = await asyncio.gather(
        _check_mx(domain),
        _check_opa_source(source_url, tenant_id),
    )

    deliverable = domain_has_mx and opa_source_ok

    # Confidence: MX contributes 0.6, OPA permit contributes 0.4
    confidence_score = round(
        (0.6 if domain_has_mx else 0.0) +
        (0.4 if opa_source_ok  else 0.0),
        3,
    )

    blocked_reason = None
    if not domain_has_mx:
        blocked_reason = f"Domain {domain!r} has no MX record — email undeliverable"
    elif not opa_source_ok:
        blocked_reason = f"Source URL {source_url!r} not permitted by OPA policy for tenant {tenant_id}"

    # HC-6: convert email to HMAC immediately; do not propagate raw value
    email_hmac    = _hmac_hex(email)
    content_hash  = _provenance_hash(email, source_url, method)

    log.info(
        "crm.contact.verifier: domain=%s mx=%s opa=%s confidence=%.2f tenant=%s",
        domain, domain_has_mx, opa_source_ok, confidence_score, tenant_id,
    )

    return {
        "deliverable":      deliverable,
        "domain_has_mx":    domain_has_mx,
        "opa_source_ok":    opa_source_ok,
        "email_hmac":       email_hmac,       # HC-6: raw email never returned
        "content_hash":     content_hash,
        "confidence_score": confidence_score,
        "blocked_reason":   blocked_reason,
    }


register_tool(SPEC, handle)
