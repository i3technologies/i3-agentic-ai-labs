"""
platform/audit/tests/test_audit_pipeline.py — WORM audit pipeline unit tests (IMP-09)

Covers:
  - AuditEvent field validation (HC-4 tenant_id, HC-6 actor_id)
  - sign() / verify() round-trip
  - Canonical payload stability
  - Tamper detection (mutated field, wrong secret)
  - Chain linking (prev_hash propagation)
  - AuditWriter (mocked S3)
  - tamper_check.verify_partition (happy-path and tampered-event detection)
  - CLI argument parsing
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ── Set required env vars before any module imports ─────────────────────
os.environ.setdefault("AUDIT_S3_BUCKET", "test-audit-bucket")
os.environ.setdefault(
    "AUDIT_HMAC_SECRET",
    "a" * 64,  # 64-char hex placeholder for testing
)

# conftest.py registers platform/audit/ under _i3_audit_ to avoid
# shadowing stdlib's `platform` module (see conftest.py).
import importlib

_audit_models = importlib.import_module("_i3_audit_.models")
_audit_writer = importlib.import_module("_i3_audit_.writer")
_audit_tamper = importlib.import_module("_i3_audit_.tamper_check")
_audit_cli    = importlib.import_module("_i3_audit_.cli")

AuditEvent       = _audit_models.AuditEvent
Outcome          = _audit_models.Outcome
RiskTier         = _audit_models.RiskTier
AuditWriter      = _audit_writer.AuditWriter
_event_key       = _audit_writer._event_key
_manifest_key    = _audit_writer._manifest_key
verify_partition = _audit_tamper.verify_partition
build_parser     = _audit_cli.build_parser
cli_main         = _audit_cli.main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT_ID   = uuid.UUID("00000000-0000-0000-0000-000000000001")
TENANT_SLUG = "test-tenant"
SECRET      = bytes.fromhex("a" * 64)

# Valid 64-char HMAC-SHA256 hex actor id
ACTOR_HMAC  = "b" * 64


def make_event(**kwargs) -> AuditEvent:
    defaults = {
        "tenant_id":     TENANT_ID,
        "tenant_slug":   TENANT_SLUG,
        "actor_id":      ACTOR_HMAC,
        "actor_role":    "admin",
        "service":       "evalos",
        "action":        "exam.submit",
        "resource_type": "Exam",
        "resource_id":   "exam-001",
        "risk_tier":     RiskTier.MEDIUM,
        "outcome":       Outcome.SUCCESS,
    }
    defaults.update(kwargs)
    return AuditEvent(**defaults)


# ---------------------------------------------------------------------------
# AuditEvent model validation
# ---------------------------------------------------------------------------

class TestAuditEventValidation:
    def test_valid_event_constructs(self):
        ev = make_event()
        assert ev.tenant_id == TENANT_ID
        assert ev.actor_id  == ACTOR_HMAC

    def test_actor_id_must_be_64_hex_chars(self):
        # Use a 64-char string with non-hex chars so the validator fires
        invalid_hmac = "z" * 64
        with pytest.raises(ValueError, match="HC-6"):
            make_event(actor_id=invalid_hmac)

    def test_actor_id_uppercase_hex_accepted_and_lowercased(self):
        """Upper-case hex digits must be accepted and normalised to lower."""
        ev = make_event(actor_id="B" * 64)
        assert ev.actor_id == "b" * 64

    def test_actor_id_non_hex_rejected(self):
        with pytest.raises(ValueError):
            make_event(actor_id="g" * 64)

    def test_hc4_tenant_id_required(self):
        """tenant_id must be provided — no default."""
        with pytest.raises(Exception):
            AuditEvent(
                # tenant_id deliberately omitted
                tenant_slug=TENANT_SLUG,
                actor_id=ACTOR_HMAC,
                actor_role="admin",
                service="evalos",
                action="exam.submit",
                resource_type="Exam",
                resource_id="exam-001",
                risk_tier=RiskTier.LOW,
                outcome=Outcome.SUCCESS,
            )

    def test_risk_tier_enum_values(self):
        for tier in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            ev = make_event(risk_tier=RiskTier(tier))
            assert ev.risk_tier.value == tier

    def test_outcome_enum_values(self):
        for outcome in ("SUCCESS", "FAILURE", "DENIED", "PARTIAL", "UNKNOWN"):
            ev = make_event(outcome=Outcome(outcome))
            assert ev.outcome.value == outcome


# ---------------------------------------------------------------------------
# sign / verify
# ---------------------------------------------------------------------------

class TestSignAndVerify:
    def test_sign_sets_event_hmac(self):
        ev = make_event()
        assert ev.event_hmac == ""
        ev.sign(SECRET)
        assert len(ev.event_hmac) == 64
        assert all(c in "0123456789abcdef" for c in ev.event_hmac)

    def test_verify_passes_after_sign(self):
        ev = make_event()
        ev.sign(SECRET)
        assert ev.verify(SECRET) is True

    def test_verify_fails_with_wrong_secret(self):
        ev = make_event()
        ev.sign(SECRET)
        wrong_secret = bytes.fromhex("f" * 64)
        assert ev.verify(wrong_secret) is False

    def test_verify_fails_after_payload_mutation(self):
        ev = make_event()
        ev.sign(SECRET)
        ev.action = "admin.delete_all"  # mutate after signing
        assert ev.verify(SECRET) is False

    def test_canonical_payload_is_stable(self):
        """Same event produced twice must give identical canonical bytes."""
        fixed_time = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        ev1 = make_event(occurred_at=fixed_time)
        ev2 = make_event(occurred_at=fixed_time)
        # Set matching event_ids
        ev2.event_id = ev1.event_id
        assert ev1.canonical_payload() == ev2.canonical_payload()

    def test_sign_returns_self(self):
        ev = make_event()
        result = ev.sign(SECRET)
        assert result is ev


# ---------------------------------------------------------------------------
# Chain linking
# ---------------------------------------------------------------------------

class TestChainLinking:
    def test_first_event_prev_hash_is_genesis(self):
        ev = make_event()
        ev.sign(SECRET)
        assert ev.prev_hash == "GENESIS"

    def test_second_event_prev_hash_is_first_event_hmac(self):
        ev1 = make_event()
        ev1.sign(SECRET)

        ev2 = make_event()
        ev2.prev_hash = ev1.event_hmac
        ev2.sign(SECRET)

        assert ev2.prev_hash == ev1.event_hmac


# ---------------------------------------------------------------------------
# AuditWriter (mocked S3)
# ---------------------------------------------------------------------------

def _make_s3_mock_empty():
    """Return a mock S3 client that has no existing objects."""
    from botocore.exceptions import ClientError
    mock = MagicMock()

    def get_object_no_such_key(**kwargs):
        raise ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject")

    mock.get_object.side_effect = get_object_no_such_key
    mock.put_object.return_value = {}
    return mock


class TestAuditWriter:
    def test_write_calls_put_object_twice(self):
        """One put_object for events, one for manifest."""
        s3_mock = _make_s3_mock_empty()
        writer  = AuditWriter(bucket="test-bucket", hmac_secret=SECRET)
        writer._s3 = s3_mock

        ev = make_event()
        writer.write(ev)

        assert s3_mock.put_object.call_count == 2

    def test_write_event_has_hmac_set(self):
        """After write(), event_hmac must be non-empty."""
        s3_mock = _make_s3_mock_empty()
        writer  = AuditWriter(bucket="test-bucket", hmac_secret=SECRET)
        writer._s3 = s3_mock

        ev = make_event()
        writer.write(ev)
        assert len(ev.event_hmac) == 64

    def test_manifest_uploaded_as_valid_json(self):
        s3_mock = _make_s3_mock_empty()
        writer  = AuditWriter(bucket="test-bucket", hmac_secret=SECRET)
        writer._s3 = s3_mock

        ev = make_event()
        writer.write(ev)

        # Find manifest put call
        manifest_call = next(
            c for c in s3_mock.put_object.call_args_list
            if "manifest.json" in c.kwargs.get("Key", "")
        )
        body = manifest_call.kwargs["Body"]
        manifest = json.loads(body)
        assert manifest["count"] == 1
        assert len(manifest["events"]) == 1
        assert manifest["tenant_slug"] == TENANT_SLUG

    def test_object_lock_mode_applied(self):
        s3_mock = _make_s3_mock_empty()
        os.environ["AUDIT_LOCK_MODE"] = "GOVERNANCE"
        writer = AuditWriter(bucket="test-bucket", hmac_secret=SECRET)
        writer._s3 = s3_mock

        writer.write(make_event())

        for call in s3_mock.put_object.call_args_list:
            assert call.kwargs.get("ObjectLockMode") == "GOVERNANCE"

        # Restore
        os.environ["AUDIT_LOCK_MODE"] = "COMPLIANCE"


# ---------------------------------------------------------------------------
# verify_partition
# ---------------------------------------------------------------------------

def _make_s3_with_partition(events: list[AuditEvent], secret: bytes):
    """
    Build a mock S3 client pre-populated with the given events
    serialised and manifested as the writer would produce them.
    """
    from botocore.exceptions import ClientError

    # Build NDJSON gz
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        for ev in events:
            gz.write((ev.model_dump_json() + "\n").encode())
    events_bytes = buf.getvalue()

    # Build manifest
    cumulative = "GENESIS"
    man_events = []
    for ev in events:
        cumulative = hashlib.sha256((cumulative + ev.event_hmac).encode()).hexdigest()
        man_events.append({"event_id": str(ev.event_id), "event_hmac": ev.event_hmac})

    manifest = {
        "count":           len(events),
        "events":          man_events,
        "cumulative_hash": cumulative,
        "tenant_slug":     events[0].tenant_slug,
        "date":            events[0].occurred_at.strftime("%Y-%m-%d"),
    }

    date_str = events[0].occurred_at.strftime("%Y-%m-%d")
    tenant   = events[0].tenant_slug

    ev_key   = _event_key(tenant, date_str)
    man_key  = _manifest_key(tenant, date_str)

    def get_object(**kwargs):
        key = kwargs["Key"]
        if key == ev_key:
            return {"Body": io.BytesIO(events_bytes)}
        if key == man_key:
            return {"Body": io.BytesIO(json.dumps(manifest).encode())}
        raise ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject")

    mock = MagicMock()
    mock.get_object.side_effect = get_object
    return mock, manifest


class TestVerifyPartition:
    def _build_chain(self, n: int) -> list[AuditEvent]:
        events = []
        for i in range(n):
            ev = make_event(
                occurred_at=datetime(2025, 6, 1, 12, i, 0, tzinfo=timezone.utc)
            )
            if events:
                ev.prev_hash = events[-1].event_hmac
            ev.sign(SECRET)
            events.append(ev)
        return events

    def test_clean_chain_passes(self):
        events = self._build_chain(3)
        s3_mock, _ = _make_s3_with_partition(events, SECRET)
        result = verify_partition(
            s3_mock, "test-bucket", SECRET, TENANT_SLUG, "2025-06-01"
        )
        assert result.ok
        assert result.checked == 3

    def test_tampered_event_hmac_detected(self):
        events = self._build_chain(3)
        # Mutate the stored event_hmac on the second event
        events[1].event_hmac = "c" * 64
        s3_mock, _ = _make_s3_with_partition(events, SECRET)
        result = verify_partition(
            s3_mock, "test-bucket", SECRET, TENANT_SLUG, "2025-06-01"
        )
        assert not result.ok
        assert any("HMAC mismatch" in e for e in result.errors)

    def test_broken_chain_detected(self):
        events = self._build_chain(3)
        # Break chain: set second event's prev_hash to wrong value
        events[1].prev_hash = "d" * 64
        # Re-sign so its own HMAC is "valid" for its mutated payload
        events[1].sign(SECRET)
        s3_mock, _ = _make_s3_with_partition(events, SECRET)
        result = verify_partition(
            s3_mock, "test-bucket", SECRET, TENANT_SLUG, "2025-06-01"
        )
        assert not result.ok
        assert any("chain broken" in e for e in result.errors)

    def test_missing_partition_is_skipped(self):
        from botocore.exceptions import ClientError

        mock = MagicMock()
        mock.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject"
        )
        result = verify_partition(
            mock, "test-bucket", SECRET, TENANT_SLUG, "2099-01-01"
        )
        assert result.ok
        assert result.checked == 0


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

class TestCLIParser:
    def test_who_subcommand_parsed(self):
        parser = build_parser()
        args   = parser.parse_args([
            "who", ACTOR_HMAC,
            "--date", "2025-06-01",
            "--tenant", "acme",
        ])
        assert args.command     == "who"
        assert args.actor_hmac  == ACTOR_HMAC
        assert args.date        == "2025-06-01"
        assert args.tenant      == "acme"

    def test_who_requires_date_or_start(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["who", ACTOR_HMAC, "--tenant", "acme"])

    def test_who_start_requires_end(self, capsys):
        # argparse.error() calls sys.exit(2) — expect SystemExit
        with pytest.raises(SystemExit) as exc_info:
            cli_main([
                "who", ACTOR_HMAC,
                "--start", "2025-06-01",
                "--tenant", "acme",
            ])
        assert exc_info.value.code != 0

    def test_verify_subcommand_parsed(self):
        parser = build_parser()
        args   = parser.parse_args([
            "verify",
            "--start", "2025-06-01",
            "--end",   "2025-06-30",
            "--tenant", "acme",
        ])
        assert args.command == "verify"
        assert args.start   == "2025-06-01"
        assert args.tenant  == "acme"

    def test_ndjson_flag(self):
        parser = build_parser()
        args   = parser.parse_args([
            "who", ACTOR_HMAC,
            "--date", "2025-06-01",
            "--ndjson",
        ])
        assert args.ndjson is True

    def test_action_filter(self):
        parser = build_parser()
        args   = parser.parse_args([
            "who", ACTOR_HMAC,
            "--date", "2025-06-01",
            "--action", "exam.submit",
        ])
        assert args.action == "exam.submit"


# ---------------------------------------------------------------------------
# Retention configuration (legal open question)
# ---------------------------------------------------------------------------

class TestRetentionConfig:
    def test_default_retention_days_is_2557(self):
        os.environ.pop("AUDIT_RETENTION_DAYS", None)
        assert _audit_writer._get_retention_days() == 2557

    def test_custom_retention_days(self):
        os.environ["AUDIT_RETENTION_DAYS"] = "1825"
        assert _audit_writer._get_retention_days() == 1825
        os.environ.pop("AUDIT_RETENTION_DAYS")

    def test_invalid_retention_days_raises(self):
        os.environ["AUDIT_RETENTION_DAYS"] = "not-a-number"
        with pytest.raises(ValueError):
            _audit_writer._get_retention_days()
        os.environ.pop("AUDIT_RETENTION_DAYS")

    def test_default_lock_mode_is_compliance(self):
        os.environ.pop("AUDIT_LOCK_MODE", None)
        assert _audit_writer._get_lock_mode() == "COMPLIANCE"

    def test_governance_lock_mode_accepted(self):
        os.environ["AUDIT_LOCK_MODE"] = "GOVERNANCE"
        assert _audit_writer._get_lock_mode() == "GOVERNANCE"
        os.environ.pop("AUDIT_LOCK_MODE")

    def test_invalid_lock_mode_raises(self):
        os.environ["AUDIT_LOCK_MODE"] = "UNDEFINED"
        with pytest.raises(ValueError):
            _audit_writer._get_lock_mode()
        os.environ.pop("AUDIT_LOCK_MODE")
