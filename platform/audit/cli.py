"""
platform/audit/cli.py — i3-audit command-line query tool (IMP-09)

Provides: i3-audit who <actor_hmac> --date <YYYY-MM-DD> --tenant <slug>

Reads audit event objects from S3 and filters by actor_id HMAC, date, and
tenant.  Output is written as pretty-printed JSON lines to stdout.

Usage
-----
  # Query all actions by a specific actor on a given date for one tenant:
  i3-audit who <64-char-hmac> --date 2025-06-01 --tenant acme

  # Query all actions by an actor across a date range:
  i3-audit who <64-char-hmac> --start 2025-06-01 --end 2025-06-30 --tenant acme

  # Omit --tenant to search across all tenants (requires LIST permission on bucket):
  i3-audit who <64-char-hmac> --date 2025-06-01

  # Filter by action verb (partial match):
  i3-audit who <64-char-hmac> --date 2025-06-01 --tenant acme --action exam.submit

  # Output NDJSON (one JSON object per line, no pretty-print):
  i3-audit who <64-char-hmac> --date 2025-06-01 --tenant acme --ndjson

Environment variables
---------------------
Same as writer.py: AUDIT_S3_BUCKET, AUDIT_HMAC_SECRET, AUDIT_S3_ENDPOINT_URL,
AUDIT_S3_REGION.

Entry point
-----------
Registered as `i3-audit` via pyproject.toml / setup.cfg:
  [project.scripts]
  i3-audit = platform.audit.cli:main
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
from datetime import date, timedelta
from typing import Iterator

import boto3
from botocore.exceptions import ClientError

from .writer import (
    _event_key,
    _get_hmac_secret,
    _require_env,
    _s3_client,
)
from .tamper_check import _list_tenants

import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_range(start: date, end: date) -> Iterator[str]:
    current = start
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def _load_events_raw(
    s3_client, bucket: str, tenant: str, date_str: str
) -> list[dict]:
    key = _event_key(tenant, date_str)
    try:
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        raw  = resp["Body"].read()
        with gzip.open(io.BytesIO(raw), "rb") as gz:
            content = gz.read()
        return [json.loads(ln) for ln in content.splitlines() if ln.strip()]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            return []
        raise


# ---------------------------------------------------------------------------
# Subcommand: who
# ---------------------------------------------------------------------------

def cmd_who(args: argparse.Namespace) -> int:
    """
    Query audit events for a given actor_id HMAC.

    Exits 0 if at least one event matched; 1 if none found; 2 on error.
    """
    bucket = os.environ.get("AUDIT_S3_BUCKET")
    if not bucket:
        print("ERROR: AUDIT_S3_BUCKET is not set", file=sys.stderr)
        return 2

    s3 = _s3_client()

    # Resolve tenant list
    if args.tenant:
        tenants = [args.tenant]
    else:
        tenants = _list_tenants(s3, bucket)
        if not tenants:
            print("WARNING: No tenant partitions found in bucket.", file=sys.stderr)
            return 1

    # Resolve date range
    if args.date:
        start_d = end_d = date.fromisoformat(args.date)
    else:
        start_d = date.fromisoformat(args.start)
        end_d   = date.fromisoformat(args.end)

    actor_query = args.actor_hmac.lower().strip()
    action_filter = (args.action or "").lower()

    matched: list[dict] = []

    for tenant in tenants:
        for date_str in _date_range(start_d, end_d):
            events = _load_events_raw(s3, bucket, tenant, date_str)
            for ev in events:
                # Actor match (exact HMAC)
                if ev.get("actor_id", "").lower() != actor_query:
                    continue
                # Action filter (substring)
                if action_filter and action_filter not in ev.get("action", "").lower():
                    continue
                matched.append(ev)

    if not matched:
        print(
            f"No audit events found for actor_hmac={actor_query!r} "
            f"tenant={args.tenant or 'ALL'} date(s)={start_d}–{end_d}",
            file=sys.stderr,
        )
        return 1

    # Output
    for ev in matched:
        if args.ndjson:
            print(json.dumps(ev, default=str))
        else:
            print(json.dumps(ev, indent=2, default=str))
            print()

    print(
        f"# {len(matched)} event(s) matched.",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: verify
# ---------------------------------------------------------------------------

def cmd_verify(args: argparse.Namespace) -> int:
    """
    Thin CLI wrapper around the tamper_check verifier for ad-hoc use.
    """
    from .tamper_check import main as tamper_main
    verify_args = ["--start", args.start, "--end", args.end]
    if args.tenant:
        verify_args += ["--tenant", args.tenant]
    return tamper_main(verify_args)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="i3-audit",
        description=(
            "i3 Platform WORM audit query tool (IMP-09). "
            "Query, filter, and verify append-only audit logs."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── who ────────────────────────────────────────────────────────────────
    who_p = sub.add_parser(
        "who",
        help="Query audit events for a given actor (HMAC-SHA256 of their identifier).",
    )
    who_p.add_argument(
        "actor_hmac",
        help=(
            "64-char HMAC-SHA256 hex digest of the actor's identifier. "
            "Compute with: echo -n '<id>' | openssl dgst -sha256 -hmac $AUDIT_HMAC_SECRET"
        ),
    )
    date_group = who_p.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Single date to query.",
    )
    date_group.add_argument(
        "--start",
        metavar="YYYY-MM-DD",
        help="Start of date range (used with --end).",
    )
    who_p.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        help="End of date range (inclusive, used with --start).",
    )
    who_p.add_argument(
        "--tenant",
        metavar="SLUG",
        default="",
        help="Tenant slug to filter on. Omit to search all tenants.",
    )
    who_p.add_argument(
        "--action",
        metavar="VERB",
        default="",
        help="Filter by action verb (substring match, e.g. 'exam.submit').",
    )
    who_p.add_argument(
        "--ndjson",
        action="store_true",
        default=False,
        help="Output NDJSON (one record per line) instead of pretty-print.",
    )

    # ── verify ─────────────────────────────────────────────────────────────
    ver_p = sub.add_parser(
        "verify",
        help="Run tamper-evidence checks on a date range.",
    )
    ver_p.add_argument("--start", required=True, metavar="YYYY-MM-DD")
    ver_p.add_argument("--end",   required=True, metavar="YYYY-MM-DD")
    ver_p.add_argument(
        "--tenant",
        default="all",
        help="Tenant slug or 'all'.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv)

    if args.command == "who":
        # Validate --start / --end pairing
        if args.start and not args.end:
            parser.error("--end is required when --start is specified")
        return cmd_who(args)

    if args.command == "verify":
        return cmd_verify(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
