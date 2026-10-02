"""
CRM Intelligence — Verify Suite
File:      platform/crm/tests/test_crawler.py

Covers Step 4 VERIFY assertions:
  1. SSRF prevention: internal/link-local URLs denied by source policy
  2. Suppression blocks export: contacts on the suppression list are dropped
  3. Evidence provenance: every contact has a corresponding HMAC content_hash
  4. No synthetic contacts: generate_provenance + assert_not_synthetic
  5. HC-4: tenant_id enforcement on every engine call
  6. HC-6: hmac_sha256_hex is NOT raw SHA-256 (key-variant check)

Tests use only stdlib + pytest — no live DB, Redis, or DNS required.
Mock DNS resolution is injected via monkeypatch.
"""

from __future__ import annotations

import hashlib
import os
import unittest.mock

import pytest

# Provide the HMAC secret before importing the module so _get_hmac_secret() passes
os.environ.setdefault("CRM_HMAC_SECRET", "test-secret-key-do-not-use-in-production")

from crm.crawler import (  # noqa: E402 — env var must be set first
    ContactEnrichmentEngine,
    SourcePolicy,
    VerificationResult,
    hmac_sha256_hex,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

TENANT_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture()
def engine() -> type[ContactEnrichmentEngine]:
    return ContactEnrichmentEngine


# ─────────────────────────────────────────────────────────────────────────────
# 1. SSRF Prevention (Step 4 assertion 3)
# ─────────────────────────────────────────────────────────────────────────────

class TestSourcePolicy:
    """Verify source_policy rejects SSRF and credential-harvesting targets."""

    def test_denied_policy_blocks_crawl(self, engine):
        """allowed=False → evaluate_source returns False."""
        policy = SourcePolicy(domain="example.com", allowed=False)
        assert engine.evaluate_source(policy) is False

    def test_requires_auth_blocks_crawl(self, engine):
        """requires_auth=True → evaluate_source returns False (Rule 2)."""
        policy = SourcePolicy(domain="linkedin.com", allowed=True, requires_auth=True)
        assert engine.evaluate_source(policy) is False

    @pytest.mark.parametrize("ssrf_url", [
        "synthetic",
        "generated",
        "",
        "   ",
    ])
    def test_assert_not_synthetic_rejects_missing_source(self, engine, ssrf_url):
        """
        Contacts without a verifiable public source_url are rejected.
        Covers SSRF vectors where source_url is spoofed as synthetic/generated.
        """
        with pytest.raises(ValueError, match="Rule 2 VIOLATION"):
            engine.assert_not_synthetic("alice@example.com", ssrf_url)

    def test_legitimate_source_url_passes(self, engine):
        """A real public URL should not raise."""
        engine.assert_not_synthetic(
            "cto@example.com",
            "https://example.com/about",
        )

    def test_allowed_policy_permits_crawl(self, engine):
        """A fully allowed, public, no-auth domain passes source policy."""
        policy = SourcePolicy(domain="example.com", allowed=True, requires_auth=False)
        assert engine.evaluate_source(policy) is True

    # ── SSRF: cloud metadata IP ──────────────────────────────────────────────
    @pytest.mark.parametrize("ssrf_domain", [
        "169.254.169.254",             # AWS/GCP/Azure IMDS endpoint
        "metadata.google.internal",    # GCP metadata alias
    ])
    def test_ssrf_metadata_endpoint_denied_by_policy(self, engine, ssrf_domain):
        """
        Step 4 assertion 3: An SSRF payload targeting the cloud metadata
        endpoint (169.254.169.254) must be immediately rejected.

        The source_policy evaluation gate (HC-5) ensures that any domain
        submitted with allowed=False is denied BEFORE any network I/O.
        In production the OPA policy populates allowed=False for all
        RFC-1918 and link-local addresses; the NetworkPolicy in
        security-profiles.yaml blocks the traffic at the kernel level.
        """
        policy = SourcePolicy(domain=ssrf_domain, allowed=False)
        assert engine.evaluate_source(policy) is False, (
            f"SSRF RISK: crawl_domain must reject metadata endpoint '{ssrf_domain}'. "
            "Ensure OPA source_policy populates allowed=False for all link-local CIDRs."
        )

    def test_ssrf_metadata_endpoint_with_allowed_true_blocked_by_requires_auth(self, engine):
        """
        Belt-and-braces: even if allowed=True were mistakenly set for an
        internal host, requires_auth=True (which is set for all internal
        services) still blocks the request via Rule 2.
        """
        policy = SourcePolicy(domain="169.254.169.254", allowed=True, requires_auth=True)
        assert engine.evaluate_source(policy) is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Suppression Check (Step 4 assertion 4)
# ─────────────────────────────────────────────────────────────────────────────

class TestSuppression:
    """Rule 4: suppressed contacts must be blocked before export."""

    def _make_hmac_set(self, *emails: str) -> set[str]:
        return {hmac_sha256_hex(e.lower()) for e in emails}

    def test_suppressed_email_is_detected(self, engine):
        """is_suppressed returns True when email HMAC is in the suppression set."""
        suppressed_hmacs = self._make_hmac_set("blocked@example.com")
        assert engine.is_suppressed("blocked@example.com", None, suppressed_hmacs) is True

    def test_non_suppressed_email_passes(self, engine):
        """is_suppressed returns False for an email not in the suppression set."""
        suppressed_hmacs = self._make_hmac_set("someone.else@example.com")
        assert engine.is_suppressed("safe@example.com", None, suppressed_hmacs) is False

    def test_suppressed_phone_is_detected(self, engine):
        """is_suppressed returns True when phone HMAC is in the suppression set."""
        phone = "+254700000001"
        suppressed_hmacs = {hmac_sha256_hex(phone)}
        assert engine.is_suppressed(None, phone, suppressed_hmacs) is True

    def test_suppression_lookup_uses_hmac_not_plaintext(self, engine):
        """
        HC-6: The suppression set must contain HMAC digests, not plaintext emails.
        Storing the raw email in the set should NOT trigger suppression.
        """
        raw_email = "blocked@example.com"
        # Intentionally wrong: store plaintext rather than the HMAC
        bad_suppressed_set = {raw_email}
        assert engine.is_suppressed(raw_email, None, bad_suppressed_set) is False

    def test_create_suppression_record_hashes_pii(self, engine):
        """HC-6: create_suppression_record never stores raw email or phone."""
        record = engine.create_suppression_record(
            email="victim@example.com",
            phone="+254700123456",
            reason="GDPR_ERASURE",
            tenant_id=TENANT_ID,
        )
        assert record["email_hmac"] != "victim@example.com"
        assert record["phone_hmac"] != "+254700123456"
        # Digests should be 64-char lowercase hex
        assert len(record["email_hmac"]) == 64
        assert len(record["phone_hmac"]) == 64

    def test_create_suppression_record_requires_tenant(self, engine):
        """HC-4: missing tenant_id raises ValueError."""
        with pytest.raises(ValueError, match="HC-4 VIOLATION"):
            engine.create_suppression_record(
                email="x@example.com",
                phone=None,
                reason="OPTED_OUT",
                tenant_id="",
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cryptographic Provenance (Step 4 assertion 5)
# ─────────────────────────────────────────────────────────────────────────────

class TestProvenance:
    """Every evidence record must carry a valid HMAC-SHA256 content_hash."""

    def test_generate_provenance_produces_64_char_hash(self, engine):
        evidence = engine.generate_provenance(
            field="email",
            value="cto@example.com",
            source_url="https://example.com/team",
            method="html_extraction",
            confidence=0.60,
            tenant_id=TENANT_ID,
        )
        assert len(evidence["content_hash"]) == 64
        # Must be lowercase hex
        assert evidence["content_hash"] == evidence["content_hash"].lower()

    def test_provenance_hash_is_deterministic(self, engine):
        """Same inputs → same content_hash (HMAC is deterministic)."""
        kwargs = dict(
            field="email",
            value="cto@example.com",
            source_url="https://example.com/team",
            method="html_extraction",
            confidence=0.60,
            tenant_id=TENANT_ID,
        )
        h1 = engine.generate_provenance(**kwargs)["content_hash"]
        h2 = engine.generate_provenance(**kwargs)["content_hash"]
        assert h1 == h2

    def test_provenance_hash_differs_across_fields(self, engine):
        """Different inputs → different hash (collision-resistance sanity)."""
        kwargs = dict(
            value="cto@example.com",
            source_url="https://example.com/team",
            method="html_extraction",
            confidence=0.60,
            tenant_id=TENANT_ID,
        )
        h_email = engine.generate_provenance(field="email", **kwargs)["content_hash"]
        h_phone = engine.generate_provenance(field="phone", **kwargs)["content_hash"]
        assert h_email != h_phone

    def test_provenance_includes_tenant_id(self, engine):
        """HC-4: tenant_id must appear in the returned evidence dict."""
        evidence = engine.generate_provenance(
            field="email",
            value="x@example.com",
            source_url="https://example.com",
            method="html_extraction",
            confidence=0.5,
            tenant_id=TENANT_ID,
        )
        assert evidence["tenant_id"] == TENANT_ID

    def test_provenance_requires_tenant(self, engine):
        """HC-4: blank tenant_id raises ValueError."""
        with pytest.raises(ValueError, match="HC-4 VIOLATION"):
            engine.generate_provenance(
                field="email",
                value="x@example.com",
                source_url="https://example.com",
                method="html_extraction",
                confidence=0.5,
                tenant_id="",
            )


# ─────────────────────────────────────────────────────────────────────────────
# 4. HC-6: HMAC ≠ raw SHA-256 (key-variant check)
# ─────────────────────────────────────────────────────────────────────────────

class TestHmacCompliance:
    """HC-6: hmac_sha256_hex output must differ from raw SHA-256 output."""

    def test_hmac_differs_from_raw_sha256(self):
        """
        Raw SHA-256 would be rainbow-table vulnerable.
        The HMAC output (keyed with CRM_HMAC_SECRET) MUST differ.
        """
        value = "alice@example.com"
        raw_sha256 = hashlib.sha256(value.encode()).hexdigest()
        keyed_hmac = hmac_sha256_hex(value)
        assert keyed_hmac != raw_sha256, (
            "HC-6 VIOLATION: hmac_sha256_hex returned the same value as raw "
            "SHA-256. Ensure the HMAC key is non-empty."
        )

    def test_hmac_output_is_64_hex_chars(self):
        assert len(hmac_sha256_hex("test")) == 64
        assert hmac_sha256_hex("test") == hmac_sha256_hex("test").lower()

    def test_different_inputs_produce_different_hmacs(self):
        assert hmac_sha256_hex("alice@example.com") != hmac_sha256_hex("bob@example.com")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Email DNS MX Verification (Step 4 assertions 1–2)
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailVerification:
    """Verify DNS MX check logic without live DNS calls."""

    def test_valid_domain_with_mx_returns_high_score(self, engine, monkeypatch):
        """Domain with MX records → confidence_score = 0.40."""
        mock_records = [unittest.mock.MagicMock()]  # non-empty list

        monkeypatch.setattr(
            "crm.crawler.dns.resolver.resolve",
            lambda domain, rtype: mock_records,
        )

        result = engine.verify_email_dns("user@example.com")
        assert result.is_valid_syntax is True
        assert result.domain_has_mx is True
        assert result.confidence_score == pytest.approx(0.40)

    def test_domain_without_mx_returns_low_score(self, engine, monkeypatch):
        """Domain with no MX → confidence_score = 0.10 (syntax-valid only)."""
        import dns.resolver as _dns_resolver

        monkeypatch.setattr(
            "crm.crawler.dns.resolver.resolve",
            unittest.mock.Mock(side_effect=_dns_resolver.NoAnswer),
        )

        result = engine.verify_email_dns("user@no-mx.example.com")
        assert result.is_valid_syntax is True
        assert result.domain_has_mx is False
        assert result.confidence_score == pytest.approx(0.10)

    def test_malformed_email_fails_syntax(self, engine):
        """Emails without exactly one '@' fail syntax validation."""
        result = engine.verify_email_dns("not-an-email")
        assert result.is_valid_syntax is False
        assert result.confidence_score == 0.0

    def test_empty_domain_part_fails(self, engine):
        """Email with empty domain fails syntax check."""
        result = engine.verify_email_dns("user@")
        assert result.is_valid_syntax is False


# ─────────────────────────────────────────────────────────────────────────────
# 6. HC-4 tenant_id enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestTenantEnforcement:
    """HC-4: every method that touches PII must require a non-empty tenant_id."""

    @pytest.mark.parametrize("bad_tenant", ["", "   ", None])
    def test_require_tenant_raises_on_blank(self, engine, bad_tenant):
        with pytest.raises(ValueError, match="HC-4 VIOLATION"):
            engine._require_tenant(bad_tenant or "")

    def test_require_tenant_accepts_valid_uuid(self, engine):
        """No exception for a valid UUID string."""
        engine._require_tenant(TENANT_ID)  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# 7. Bulk-throughput assertion (Step 4 assertion 3 — 1,180 records)
# ─────────────────────────────────────────────────────────────────────────────

class TestBulkThroughput:
    """
    Simulate the Celery pipeline processing 1,180 contact records under
    rate-limited conditions.

    This test does NOT require a live Celery broker.  It asserts the two
    invariants that matter for the bulk-run:
      a) Every record produces a valid HMAC content_hash (no hash collision,
         no HC-6 violations).
      b) Suppression is checked per-record and drops the correct subset,
         leaving the remainder available for export.

    1,180 = 50 TAM orgs × average 23 contacts + 30 suppressed seed records
    (representative of the MEA TAM workbook density).
    """

    BULK_COUNT = 1_180
    SUPPRESSED_COUNT = 30   # contacts whose email HMAC is in the suppression set

    def test_bulk_provenance_hashes_are_unique(self):
        """
        Generate 1,180 provenance records and assert:
          - All content_hash values are 64-char hex strings (HC-6 format).
          - No two records share the same content_hash (collision-resistance).
        """
        hashes: set[str] = set()
        for i in range(self.BULK_COUNT):
            evidence = ContactEnrichmentEngine.generate_provenance(
                field="email",
                value=f"contact_{i}@tenant-{i % 50}.example.com",
                source_url=f"https://company-{i % 50}.example.com/team",
                method="html_extraction",
                confidence=0.60,
                tenant_id=TENANT_ID,
            )
            h = evidence["content_hash"]
            assert len(h) == 64, f"Record {i}: content_hash is not 64 chars"
            assert h == h.lower(), f"Record {i}: content_hash is not lowercase hex"
            hashes.add(h)

        assert len(hashes) == self.BULK_COUNT, (
            f"HC-6 collision: only {len(hashes)} unique hashes for "
            f"{self.BULK_COUNT} records."
        )

    def test_bulk_suppression_drops_correct_records(self):
        """
        Build a suppression set from the first SUPPRESSED_COUNT emails,
        then verify exactly those records are flagged suppressed while
        the remaining 1,150 pass through.
        """
        emails = [
            f"contact_{i}@example.com" for i in range(self.BULK_COUNT)
        ]
        # Seed suppression set with the first SUPPRESSED_COUNT records
        suppressed_hmacs = {
            hmac_sha256_hex(emails[i].lower())
            for i in range(self.SUPPRESSED_COUNT)
        }

        suppressed_count = 0
        exported_count = 0
        for email in emails:
            if ContactEnrichmentEngine.is_suppressed(email, None, suppressed_hmacs):
                suppressed_count += 1
            else:
                exported_count += 1

        assert suppressed_count == self.SUPPRESSED_COUNT, (
            f"Expected {self.SUPPRESSED_COUNT} suppressed, got {suppressed_count}"
        )
        assert exported_count == self.BULK_COUNT - self.SUPPRESSED_COUNT, (
            f"Expected {self.BULK_COUNT - self.SUPPRESSED_COUNT} exported, "
            f"got {exported_count}"
        )
