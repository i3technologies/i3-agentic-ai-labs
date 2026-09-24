"""
platform/audit/tamper_check.py — WORM tamper-evidence verifier (IMP-09)

Batch job that re-reads every manifest and event object in S3 for a given
date range and verifies:

  1. Per-event HMAC: event_hmac == HMAC-SHA256(secret, canonical_payload)
  2. Chain integrity: each event's prev_hash matches the preceding event's
     event_hmac (or "GENESIS" for the first event).
  3. Manifest integrity: the stored cumulative_hash matches a freshly
     recomputed rolling SHA-256 over the event_hmac sequence.
  4. Count integrity: manifest.count == len(events) in the events object.

Any discrepancy is logged at CRITICAL level and exits with a non-zero code
so that the Kubernetes CronJob can alert on failure.

Usage (direct)
--------------
  python -m platform.audit.tamper_check \\
      --tenant all \\
      --start 2025-01-01 \\
      --end   2025-01-31

Usage (Kubernetes CronJob)
--------------------------
  See platform/audit/cronjob-tamper-check.yaml

Environment variables
---------------------
Same as writer.py: AUDIT_S3_BUCKET, AUDIT_HMAC_SECRET, AUDIT_S3_ENDPOINT_URL,
AUDIT_S3_REGION.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import logging
import os
import sys
from datetime import date, timedelta
from typing import Iterator

import boto3
from botocore.exceptions import ClientError

from .models import AuditEvent
from .writer import _get_hmac_secret, _manifest_key, _event_key, _s3_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("audit.tamper_check")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_range(start: date, end: date) -> Iterator[str]:
    """Yield YYYY-MM-DD strings from start to end inclusive."""
    current = start
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def _list_tenants(s3_client, bucket: str) -> list[str]:
    """
    Return all tenant slugs found in the audit/ prefix.
    Assumes key structure: audit/<tenant_slug>/<date>/...
    """
    tenants: set[str] = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="audit/", Delimiter="/"):
        for prefix in page.get("CommonPrefixes", []):
            # "audit/tenant-slug/"  → "tenant-slug"
            slug = prefix["Prefix"].rstrip("/").split("/")[-1]
            if slug:
                tenants.add(slug)
    return sorted(tenants)


def _load_manifest(s3_client, bucket: str, tenant: str, date_str: str) -> dict | None:
    key = _manifest_key(tenant, date_str)
    try:
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read())
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def _load_events(s3_client, bucket: str, tenant: str, date_str: str) -> list[dict]:
    key = _event_key(tenant, date_str)
    try:
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        raw  = resp["Body"].read()
        with gzip.open(io.BytesIO(raw), "rb") as gz:
            content = gz.read()
        lines = [ln for ln in content.splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            return []
        raise


# ---------------------------------------------------------------------------
# Core verification
# ---------------------------------------------------------------------------

class VerificationResult:
    def __init__(self, tenant: str, date_str: str):
        self.tenant        = tenant
        self.date_str      = date_str
        self.errors:  list[str] = []
        self.checked: int       = 0

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def fail(self, msg: str) -> None:
        self.errors.append(msg)
        logger.critical("TAMPER_DETECT tenant=%s date=%s error=%s",
                        self.tenant, self.date_str, msg)


def verify_partition(
    s3_client,
    bucket: str,
    secret: bytes,
    tenant: str,
    date_str: str,
) -> VerificationResult:
    """
    Verify a single (tenant, date) partition.
    Returns a VerificationResult describing any discrepancies.
    """
    result = VerificationResult(tenant, date_str)

    manifest = _load_manifest(s3_client, bucket, tenant, date_str)
    if manifest is None:
        # No data for this partition — not an error, just skip.
        logger.debug("No manifest for tenant=%s date=%s — skipping", tenant, date_str)
        return result

    raw_events = _load_events(s3_client, bucket, tenant, date_str)

    # Check 4: count
    expected_count = manifest.get("count", len(manifest.get("events", [])))
    if len(raw_events) != expected_count:
        result.fail(
            f"count mismatch: manifest.count={expected_count} "
            f"actual_events={len(raw_events)}"
        )

    manifest_event_list: list[dict] = manifest.get("events", [])

    cumulative = "GENESIS"
    prev_hmac  = "GENESIS"

    for idx, raw in enumerate(raw_events):
        result.checked += 1
        try:
            ev = AuditEvent.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            result.fail(f"event[{idx}] parse error: {exc}")
            continue

        # Check 2: chain prev_hash
        expected_prev = "GENESIS" if idx == 0 else raw_events[idx - 1].get("event_hmac", "")
        if ev.prev_hash != expected_prev:
            result.fail(
                f"event[{idx}] chain broken: stored prev_hash={ev.prev_hash!r} "
                f"expected={expected_prev!r}"
            )

        # Check 1: per-event HMAC
        if not ev.verify(secret):
            result.fail(
                f"event[{idx}] HMAC mismatch: event_id={ev.event_id} "
                "payload may have been mutated"
            )

        # Accumulate cumulative hash
        cumulative = hashlib.sha256(
            (cumulative + ev.event_hmac).encode()
        ).hexdigest()

        # Check manifest row
        if idx < len(manifest_event_list):
            man_row = manifest_event_list[idx]
            if man_row.get("event_id") != str(ev.event_id):
                result.fail(
                    f"event[{idx}] event_id mismatch between manifest and event object: "
                    f"manifest={man_row.get('event_id')} actual={ev.event_id}"
                )
            if man_row.get("event_hmac") != ev.event_hmac:
                result.fail(
                    f"event[{idx}] event_hmac mismatch in manifest row: "
                    f"manifest={man_row.get('event_hmac')} actual={ev.event_hmac}"
                )

        prev_hmac = ev.event_hmac

    # Check 3: cumulative hash
    stored_cumulative = manifest.get("cumulative_hash", "")
    if raw_events and cumulative != stored_cumulative:
        result.fail(
            f"cumulative_hash mismatch: stored={stored_cumulative!r} "
            f"recomputed={cumulative!r}"
        )

    if result.ok:
        logger.info(
            "VERIFIED tenant=%s date=%s events=%d PASS",
            tenant, date_str, result.checked,
        )

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit-tamper-check",
        description="Verify WORM audit log HMAC chain integrity (IMP-09).",
    )
    parser.add_argument(
        "--tenant",
        default="all",
        help="Tenant slug to verify, or 'all' to verify every tenant.",
    )
    parser.add_argument(
        "--start",
        required=True,
        type=date.fromisoformat,
        help="Start date in YYYY-MM-DD format (inclusive).",
    )
    parser.add_argument(
        "--end",
        required=True,
        type=date.fromisoformat,
        help="End date in YYYY-MM-DD format (inclusive).",
    )
    args = parser.parse_args(argv)

    bucket = os.environ.get("AUDIT_S3_BUCKET")
    if not bucket:
        logger.critical("AUDIT_S3_BUCKET is not set — aborting")
        return 1

    try:
        secret = _get_hmac_secret()
    except Exception as exc:  # noqa: BLE001
        logger.critical("Cannot load HMAC secret: %s", exc)
        return 1

    s3 = _s3_client()

    if args.tenant == "all":
        tenants = _list_tenants(s3, bucket)
        if not tenants:
            logger.warning("No tenant partitions found in bucket=%s prefix=audit/", bucket)
            return 0
    else:
        tenants = [args.tenant]

    total_checked  = 0
    total_failures = 0
    failed_partitions: list[str] = []

    for tenant in tenants:
        for date_str in _date_range(args.start, args.end):
            result = verify_partition(s3, bucket, secret, tenant, date_str)
            total_checked  += result.checked
            total_failures += len(result.errors)
            if not result.ok:
                failed_partitions.append(f"{tenant}/{date_str}")

    # Summary
    logger.info(
        "TAMPER_CHECK_SUMMARY tenants=%d date_range=%s/%s "
        "events_checked=%d failures=%d",
        len(tenants), args.start, args.end,
        total_checked, total_failures,
    )

    if total_failures:
        logger.critical(
            "TAMPER_CHECK FAILED — %d discrepancies across %d partition(s): %s",
            total_failures, len(failed_partitions),
            ", ".join(failed_partitions),
        )
        return 2

    logger.info("TAMPER_CHECK PASSED — all %d events verified", total_checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
