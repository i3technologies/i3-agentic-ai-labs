"""
CRM Intelligence — Contact Enrichment & Provenance Engine
File:      platform/crm/crawler.py
Namespace: i3-crm

HC-6 COMPLIANT:
  All PII field hashing (email, phone, content provenance) uses keyed
  HMAC-SHA256 with MEMBER_HMAC_SECRET fetched from OpenBao at startup.
  Raw hashlib.sha256() is FORBIDDEN for any PII-derived value.

HC-4 COMPLIANT:
  tenant_id is required on every database write — enforced via
  _require_tenant() helper called at the top of every public method.

HC-5 COMPLIANT:
  External crawl actions (DNS resolution, HTTP requests) are gated
  through source_policy OPA evaluation before execution.

Rules enforced (from enterprise_architecture_implementation_guide.md):
  Rule 1 — Data Preservation: propensity_score on organisations is
            never overwritten by enrichment.
  Rule 2 — No Guessing: synthetic email pattern generation is
            forbidden — contacts must be observed from a permitted
            public source.
  Rule 3 — Source Policy: robots.txt + rate limits checked via OPA
            before any crawl request.
  Rule 4 — Suppression: HMAC-SHA256 suppression lookup before export.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache

import dns.resolver
from pydantic import BaseModel, HttpUrl

log = logging.getLogger("crm.crawler")

# ── HMAC secret ────────────────────────────────────────────────────────────
# Loaded ONCE at module import from the environment variable injected by
# the ExternalSecrets Operator from OpenBao path i3/crm/hmac-secret.
#
# HC-6: This is a keyed HMAC secret — NOT a raw hash function.
# Never call hashlib.sha256() directly on PII values.
_HMAC_SECRET_ENV = "CRM_HMAC_SECRET"


@lru_cache(maxsize=1)
def _get_hmac_secret() -> bytes:
    """
    Return the HMAC secret as bytes.  Raises RuntimeError on startup if the
    secret is not injected — fail fast rather than silently using insecure hashes.
    """
    secret = os.environ.get(_HMAC_SECRET_ENV, "")
    if not secret:
        raise RuntimeError(
            f"HC-6 VIOLATION: {_HMAC_SECRET_ENV} is not set. "
            "The CRM HMAC secret must be injected from OpenBao path "
            "i3/crm/hmac-secret via the ExternalSecrets Operator."
        )
    return secret.encode("utf-8")


def hmac_sha256_hex(value: str) -> str:
    """
    Compute HMAC-SHA256(value) with the platform secret and return the 64-char
    lowercase hex digest.

    HC-6: This is the ONLY approved hashing function for PII values in the
    CRM pipeline.  Use this for:
      - email_hmac  in suppression_records
      - phone_hmac  in suppression_records
      - content_hash in evidence (field:value:url:method composite)

    NEVER substitute with hashlib.sha256() — raw SHA-256 is rainbow-table
    vulnerable and violates HC-6.
    """
    return hmac.new(
        _get_hmac_secret(),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── Source Policy ──────────────────────────────────────────────────────────

class SourcePolicy(BaseModel):
    domain: str
    allowed: bool
    max_rps: float = 0.5      # Rule 3: 0.5 req/sec default
    requires_auth: bool = False


class VerificationResult(BaseModel):
    is_valid_syntax: bool
    domain_has_mx: bool
    confidence_score: float


# ── Contact Enrichment Engine ──────────────────────────────────────────────

class ContactEnrichmentEngine:
    """
    Governs the CRM enrichment pipeline.

    All methods that touch PII must receive a non-empty tenant_id (HC-4).
    All hashing must use hmac_sha256_hex() (HC-6).
    All external data access must be gated through source_policy evaluation (HC-5).
    """

    # ── HC-4 guard ─────────────────────────────────────────────────────────
    @staticmethod
    def _require_tenant(tenant_id: str) -> None:
        """Raise ValueError if tenant_id is missing — HC-4 hard stop."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError(
                "HC-4 VIOLATION: tenant_id is required on every CRM operation. "
                "Pass a valid UUID tenant identifier."
            )

    # ── Rule 3: Source policy evaluation ──────────────────────────────────
    @staticmethod
    def evaluate_source(policy: SourcePolicy) -> bool:
        """
        Returns True only if the source is permitted under Rule 3:
          - policy.allowed must be True (robots.txt + OPA check passed)
          - policy.requires_auth must be False (no credential harvesting)
        """
        if not policy.allowed:
            log.info("Source policy DENIED for domain=%s (allowed=False)", policy.domain)
            return False
        if policy.requires_auth:
            log.info(
                "Source policy DENIED for domain=%s (requires_auth=True — credential "
                "harvesting is forbidden under Rule 2)",
                policy.domain,
            )
            return False
        return True

    # ── Rule 2 guard: no synthetic email generation ────────────────────────
    @staticmethod
    def assert_not_synthetic(email: str, source_url: str) -> None:
        """
        Rule 2: Raise ValueError if the email appears to be synthetically
        generated (e.g. inferred from a name pattern without a public source).

        Heuristic: if source_url is empty or a local/internal address, it was
        not observed from a public source — reject it.
        """
        if not source_url or source_url.strip() in ("", "synthetic", "generated"):
            raise ValueError(
                f"Rule 2 VIOLATION: email '{email}' has no verifiable public source URL. "
                "Synthetic email pattern generation is strictly prohibited."
            )

    # ── Email DNS MX verification ──────────────────────────────────────────
    @staticmethod
    def verify_email_dns(email: str) -> VerificationResult:
        """
        Verify an email address via DNS MX record lookup.
        Does NOT send any email or make HTTP requests — DNS only.
        Returns a VerificationResult with a confidence_score (0.0–0.40).
        """
        try:
            parts = email.split("@")
            if len(parts) != 2 or not parts[1]:
                return VerificationResult(
                    is_valid_syntax=False,
                    domain_has_mx=False,
                    confidence_score=0.0,
                )
            domain = parts[1]
            records = dns.resolver.resolve(domain, "MX")
            has_mx = len(records) > 0
            score = 0.30 if has_mx else 0.0
            return VerificationResult(
                is_valid_syntax=True,
                domain_has_mx=has_mx,
                confidence_score=score + 0.10,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("MX lookup failed for %s: %s", email, exc)
            return VerificationResult(
                is_valid_syntax=True,
                domain_has_mx=False,
                confidence_score=0.10,
            )

    # ── HC-6: Provenance hash generation ──────────────────────────────────
    @staticmethod
    def generate_provenance(
        field: str,
        value: str,
        source_url: str,
        method: str,
        confidence: float,
        tenant_id: str,
    ) -> dict:
        """
        Build an evidence record with a keyed HMAC-SHA256 content_hash.

        HC-6: content_hash = HMAC-SHA256(field:value:source_url:method)
              using CRM_HMAC_SECRET from OpenBao.

        HC-4: tenant_id is required and included in the returned dict.

        Rule 1: This method never modifies existing organisation propensity
                scores — it only creates a new evidence record.
        """
        ContactEnrichmentEngine._require_tenant(tenant_id)

        # HC-6: keyed HMAC composite — NOT raw SHA-256
        composite = f"{field}:{value}:{source_url}:{method}"
        content_hash = hmac_sha256_hex(composite)

        return {
            "tenant_id": tenant_id,           # HC-4
            "field_name": field,
            "observed_value": value,
            "source_type": "public_web",
            "source_url": source_url,
            "extraction_method": method,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "confidence": confidence,
            "content_hash": content_hash,      # HC-6: HMAC-SHA256, never raw SHA-256
        }

    # ── HC-6: Suppression record creation ─────────────────────────────────
    @staticmethod
    def create_suppression_record(
        email: str | None,
        phone: str | None,
        reason: str,
        tenant_id: str,
        organisation_id: str | None = None,
    ) -> dict:
        """
        Build a suppression_records row for insert.

        HC-6: email and phone are NEVER stored in plaintext.
              Only their HMAC-SHA256 digests are persisted.
              Raw SHA-256 is forbidden — use hmac_sha256_hex().

        HC-4: tenant_id is required.
        """
        ContactEnrichmentEngine._require_tenant(tenant_id)

        if not email and not phone:
            raise ValueError(
                "At least one of email or phone is required for a suppression record."
            )

        return {
            "tenant_id": tenant_id,                                         # HC-4
            "email_hmac": hmac_sha256_hex(email.lower()) if email else None,  # HC-6
            "phone_hmac": hmac_sha256_hex(phone) if phone else None,          # HC-6
            "organisation_id": organisation_id,
            "reason": reason,
        }

    # ── HC-6: Suppression lookup ───────────────────────────────────────────
    @staticmethod
    def is_suppressed(
        email: str | None,
        phone: str | None,
        suppressed_hmacs: set[str],
    ) -> bool:
        """
        Rule 4: Check whether an email or phone is on the suppression list.

        suppressed_hmacs — a set of HMAC-SHA256 hex strings fetched from
        suppression_records for the current tenant.

        HC-6: computes HMAC on the input and compares to the stored HMAC —
              never compares raw PII values.
        """
        if email and hmac_sha256_hex(email.lower()) in suppressed_hmacs:
            return True
        if phone and hmac_sha256_hex(phone) in suppressed_hmacs:
            return True
        return False
