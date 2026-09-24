"""
platform/audit/writer.py — append-only WORM audit writer (IMP-09)

Writes signed AuditEvent records as NDJSON to append-only S3-compatible
object storage with per-object retention locks.

Design decisions
----------------
* One object per (tenant_slug, UTC-date) partition keeps each file bounded
  and aligns with the auditor query pattern (--tenant + --date).
* Objects are uploaded with Object Lock in COMPLIANCE mode at the retention
  class configured via the environment / config — NEVER hardcoded.
* A manifest object (manifest.json) per partition records the ordered list
  of event_ids and the cumulative hash chain so that the tamper-check job
  can verify integrity without re-reading every object.
* The writer is synchronous; callers that need async should run it in a
  thread-pool executor.

⚠ OPEN LEGAL QUESTION (IMP-09)
-------------------------------
The default retention class / duration is not yet confirmed by legal counsel.
It is intentionally left configurable via the AUDIT_RETENTION_DAYS and
AUDIT_LOCK_MODE environment variables.  Do NOT hardcode these values until
legal sign-off is obtained.  See platform/audit/LEGAL-NOTICE.md.

Environment variables
---------------------
AUDIT_S3_ENDPOINT_URL   — S3-compatible endpoint (e.g. https://s3.example.com)
                          If unset, falls back to the default AWS endpoint.
AUDIT_S3_BUCKET         — Bucket name (must have Object Lock enabled).
AUDIT_S3_REGION         — AWS / Ceph region (default: us-east-1).
AUDIT_HMAC_SECRET       — 256-bit hex HMAC secret injected from OpenBao
                          (path: i3/audit/hmac-secret).  HC-6 compliance.
AUDIT_RETENTION_DAYS    — ⚠ OPEN LEGAL QUESTION — integer, days to retain
                          each audit object under Object Lock.
                          Default: 2557 (≈7 years) — pending legal review.
AUDIT_LOCK_MODE         — ⚠ OPEN LEGAL QUESTION — "COMPLIANCE" or "GOVERNANCE".
                          Default: COMPLIANCE — pending legal review.
"""

from __future__ import annotations

import gzip
import hashlib
import hmac as _hmac
import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .models import AuditEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Check OpenBao injection and Kubernetes secret mounts."
        )
    return val


def _get_hmac_secret() -> bytes:
    """Read AUDIT_HMAC_SECRET from the environment (OpenBao-injected)."""
    hex_secret = _require_env("AUDIT_HMAC_SECRET")
    try:
        return bytes.fromhex(hex_secret)
    except ValueError as exc:
        raise ValueError(
            "AUDIT_HMAC_SECRET must be a 256-bit (64-char) hex string. "
            "Rotate via i3/audit/hmac-secret in OpenBao."
        ) from exc


# ---------------------------------------------------------------------------
# ⚠ OPEN LEGAL QUESTION — retention parameters
# ---------------------------------------------------------------------------

_LEGAL_NOTICE = (
    "AUDIT_RETENTION_DAYS and AUDIT_LOCK_MODE have not been confirmed by "
    "legal counsel.  The current defaults (2557 days / COMPLIANCE) are "
    "placeholders.  See platform/audit/LEGAL-NOTICE.md."
)

def _get_retention_days() -> int:
    """
    ⚠ OPEN LEGAL QUESTION — return the configured retention period in days.
    Default is 2557 (≈7 years) as a conservative placeholder only.
    """
    raw = os.environ.get("AUDIT_RETENTION_DAYS", "2557")
    try:
        days = int(raw)
        if days < 1:
            raise ValueError("must be positive")
    except ValueError as exc:
        raise ValueError(
            f"AUDIT_RETENTION_DAYS='{raw}' is invalid. "
            "Set a positive integer (days). " + _LEGAL_NOTICE
        ) from exc
    return days


def _get_lock_mode() -> str:
    """
    ⚠ OPEN LEGAL QUESTION — return 'COMPLIANCE' or 'GOVERNANCE'.
    Default is COMPLIANCE as a conservative placeholder only.
    """
    mode = os.environ.get("AUDIT_LOCK_MODE", "COMPLIANCE").upper()
    if mode not in ("COMPLIANCE", "GOVERNANCE"):
        raise ValueError(
            f"AUDIT_LOCK_MODE='{mode}' must be 'COMPLIANCE' or 'GOVERNANCE'. "
            + _LEGAL_NOTICE
        )
    return mode


# ---------------------------------------------------------------------------
# Object-key helpers
# ---------------------------------------------------------------------------

def _event_key(tenant_slug: str, date: str) -> str:
    """
    Primary NDJSON object key.
    Pattern: audit/<tenant_slug>/YYYY-MM-DD/events.ndjson.gz
    """
    return f"audit/{tenant_slug}/{date}/events.ndjson.gz"


def _manifest_key(tenant_slug: str, date: str) -> str:
    """
    Manifest object key.
    Pattern: audit/<tenant_slug>/YYYY-MM-DD/manifest.json
    """
    return f"audit/{tenant_slug}/{date}/manifest.json"


# ---------------------------------------------------------------------------
# S3 client factory
# ---------------------------------------------------------------------------

def _s3_client():
    kwargs: dict = {}
    endpoint = os.environ.get("AUDIT_S3_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    region = os.environ.get("AUDIT_S3_REGION", "us-east-1")
    return boto3.client("s3", region_name=region, **kwargs)


# ---------------------------------------------------------------------------
# AuditWriter
# ---------------------------------------------------------------------------

class AuditWriter:
    """
    Append WORM audit events to S3-compatible object storage.

    Each call to ``write(event)`` appends one NDJSON line to the partition
    object for (tenant_slug, UTC-date) and updates the manifest atomically
    by re-uploading it.  Both operations apply Object Lock.

    Thread-safety: NOT thread-safe.  Use one writer instance per process
    (e.g. in a Kafka consumer or background task), or wrap with a lock.
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        hmac_secret: Optional[bytes] = None,
    ) -> None:
        self._bucket      = bucket or _require_env("AUDIT_S3_BUCKET")
        self._secret      = hmac_secret or _get_hmac_secret()
        self._s3          = _s3_client()
        self._ret_days    = _get_retention_days()
        self._lock_mode   = _get_lock_mode()

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def write(self, event: AuditEvent) -> None:
        """
        Sign *event*, append it to the tenant partition, and update the
        manifest.  The object is uploaded with an Object Lock retain-until
        date derived from the configured retention period.

        Raises on any S3 or HMAC error.
        """
        date_str = event.occurred_at.strftime("%Y-%m-%d")

        # Sign the event (sets event_hmac)
        event.sign(self._secret)

        # Fetch or initialise partition state
        existing_lines, manifest = self._load_partition(event.tenant_slug, date_str)

        # Chain: prev_hash = last event_hmac in manifest, or "GENESIS"
        if manifest.get("events"):
            event.prev_hash = manifest["events"][-1]["event_hmac"]
            # Re-sign after prev_hash is set
            event.sign(self._secret)

        ndjson_line = event.model_dump_json() + "\n"
        existing_lines.append(ndjson_line.encode())

        # Cumulative manifest hash (rolling SHA-256 of all event_hmacs)
        prev_cumulative = manifest.get("cumulative_hash", "GENESIS")
        cumulative = hashlib.sha256(
            (prev_cumulative + event.event_hmac).encode()
        ).hexdigest()

        manifest.setdefault("events", []).append(
            {"event_id": str(event.event_id), "event_hmac": event.event_hmac}
        )
        manifest["cumulative_hash"] = cumulative
        manifest["last_updated"]    = event.occurred_at.isoformat()
        manifest["tenant_slug"]     = event.tenant_slug
        manifest["date"]            = date_str
        manifest["count"]           = len(manifest["events"])

        self._upload_events(event.tenant_slug, date_str, existing_lines)
        self._upload_manifest(event.tenant_slug, date_str, manifest)

        logger.info(
            "audit_event_written event_id=%s tenant=%s action=%s outcome=%s",
            event.event_id, event.tenant_slug, event.action, event.outcome.value,
        )

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _retain_until(self) -> str:
        """ISO-8601 UTC retain-until timestamp for Object Lock."""
        until = datetime.now(tz=timezone.utc) + timedelta(days=self._ret_days)
        return until.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _load_partition(
        self, tenant_slug: str, date_str: str
    ) -> tuple[list[bytes], dict]:
        """
        Download existing NDJSON lines and manifest for the partition.
        Returns (lines, manifest_dict) — both empty/default if the partition
        does not yet exist.
        """
        ev_key  = _event_key(tenant_slug, date_str)
        man_key = _manifest_key(tenant_slug, date_str)
        lines: list[bytes] = []
        manifest: dict     = {}

        # Events object
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=ev_key)
            raw  = resp["Body"].read()
            with gzip.open(io.BytesIO(raw), "rb") as gz:
                lines = [ln + b"\n" for ln in gz.read().splitlines() if ln.strip()]
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchKey":
                raise

        # Manifest object
        try:
            resp     = self._s3.get_object(Bucket=self._bucket, Key=man_key)
            manifest = json.loads(resp["Body"].read())
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchKey":
                raise

        return lines, manifest

    def _upload_events(
        self, tenant_slug: str, date_str: str, lines: list[bytes]
    ) -> None:
        key      = _event_key(tenant_slug, date_str)
        buf      = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            for line in lines:
                gz.write(line)
        body = buf.getvalue()

        self._s3.put_object(
            Bucket                           = self._bucket,
            Key                              = key,
            Body                             = body,
            ContentType                      = "application/gzip",
            ObjectLockMode                   = self._lock_mode,
            ObjectLockRetainUntilDate        = self._retain_until(),
        )

    def _upload_manifest(
        self, tenant_slug: str, date_str: str, manifest: dict
    ) -> None:
        key  = _manifest_key(tenant_slug, date_str)
        body = json.dumps(manifest, indent=2).encode()

        self._s3.put_object(
            Bucket                           = self._bucket,
            Key                              = key,
            Body                             = body,
            ContentType                      = "application/json",
            ObjectLockMode                   = self._lock_mode,
            ObjectLockRetainUntilDate        = self._retain_until(),
        )
