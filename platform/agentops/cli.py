"""
platform/agentops/cli.py — AgentOps weekly review pack CLI

Usage
-----
  python -m platform.agentops.cli [OPTIONS]

Options
-------
  --week        ISO week label, e.g. "W42-2026". Default: current week.
  --tenants     Comma-separated tenant UUIDs to scope the report.
                Default: all tenants (reads AGENTOPS_TENANT_IDS env var).
  --ragas       Path or S3 URI to RAGAS gate-evidence JSON.
                Default: RAGAS_EVIDENCE_PATH env var or repo default.
  --out-dir     Directory to write outputs. Default: /tmp/agentops-pack
  --json-only   Write JSON pack only, skip HTML rendering.
  --html-only   Write HTML only, skip JSON dump.
  --upload      Upload outputs to S3 (AGENTOPS_S3_BUCKET must be set).

Output files
------------
  <out-dir>/agentops-<week>.json   — machine-readable review pack
  <out-dir>/agentops-<week>.html   — human-readable HTML one-pager

The CronJob invokes this as:
  python -m platform.agentops.cli --upload
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("agentops.cli")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m platform.agentops.cli",
        description="Generate the i3 AgentOps weekly review pack.",
    )
    p.add_argument(
        "--week",
        default=None,
        help="ISO week label (e.g. W42-2026). Defaults to current week.",
    )
    p.add_argument(
        "--tenants",
        default=None,
        help="Comma-separated tenant UUIDs. Default: all tenants.",
    )
    p.add_argument(
        "--ragas",
        default=None,
        help="Path or s3://bucket/key to RAGAS gate-evidence JSON.",
    )
    p.add_argument(
        "--out-dir",
        default=os.environ.get("AGENTOPS_OUT_DIR", "/tmp/agentops-pack"),
        help="Output directory (default: /tmp/agentops-pack).",
    )
    p.add_argument(
        "--json-only",
        action="store_true",
        help="Write JSON pack only; skip HTML.",
    )
    p.add_argument(
        "--html-only",
        action="store_true",
        help="Write HTML only; skip JSON.",
    )
    p.add_argument(
        "--upload",
        action="store_true",
        help="Upload outputs to S3 (requires AGENTOPS_S3_BUCKET).",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------

def _upload_to_s3(local_path: Path, week: str) -> None:
    """Upload a single file to s3://<AGENTOPS_S3_BUCKET>/agentops/<week>/<filename>."""
    import boto3

    bucket = os.environ.get("AGENTOPS_S3_BUCKET")
    if not bucket:
        raise EnvironmentError(
            "AGENTOPS_S3_BUCKET is not set. Cannot upload review pack."
        )
    endpoint = os.environ.get("AGENTOPS_S3_ENDPOINT_URL")
    region   = os.environ.get("AGENTOPS_S3_REGION", "us-east-1")
    kwargs: dict = {}
    if endpoint:
        kwargs["endpoint_url"] = endpoint

    s3     = boto3.client("s3", region_name=region, **kwargs)
    key    = f"agentops/{week}/{local_path.name}"
    ct_map = {".json": "application/json", ".html": "text/html; charset=utf-8"}
    ct     = ct_map.get(local_path.suffix, "application/octet-stream")

    s3.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={"ContentType": ct},
    )
    logger.info("Uploaded s3://%s/%s", bucket, key)


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def _run(args: argparse.Namespace) -> int:
    from .review_pack import build_pack
    from .report import render_html

    # Tenant list
    tenants: list[str] | None = None
    if args.tenants:
        tenants = [t.strip() for t in args.tenants.split(",") if t.strip()]

    # Week label
    now  = datetime.now(tz=timezone.utc)
    week = args.week or now.strftime("W%V-%Y")

    logger.info("Building AgentOps review pack for %s …", week)
    pack = await build_pack(
        tenant_ids=tenants,
        ragas_evidence_path=args.ragas,
        week_label=week,
    )

    # Output directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"agentops-{week}.json"
    html_path = out_dir / f"agentops-{week}.html"

    uploaded: list[Path] = []

    # JSON
    if not args.html_only:
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        logger.info("Written %s", json_path)
        if args.upload:
            _upload_to_s3(json_path, week)
            uploaded.append(json_path)

    # HTML
    if not args.json_only:
        html_content = render_html(pack)
        html_path.write_text(html_content, encoding="utf-8")
        logger.info("Written %s", html_path)
        if args.upload:
            _upload_to_s3(html_path, week)
            uploaded.append(html_path)

    # Summary to stdout
    print(f"\n=== AgentOps Review Pack — {week} ===")
    print(f"  Generated:      {pack['generated_at']}")
    print(f"  Tenant scope:   {pack['tenant_scope']}")
    print(f"  Agents tracked: {len(pack['autonomy_rates'])}")
    print(f"  Spend rows:     {len(pack['spend_vs_budget'])}")
    print(f"  Anomalies:      {len(pack['audit_anomalies'])}")
    print(f"  Risk items:     {len(pack['risk_register'])}")
    print(f"  Eval status:    {pack['eval_trend'].get('status', 'NO_EVIDENCE')}")
    if not args.html_only:
        print(f"  JSON:           {json_path}")
    if not args.json_only:
        print(f"  HTML:           {html_path}")
    if uploaded:
        print(f"  S3 uploads:     {len(uploaded)} file(s)")
    print()

    # Exit non-zero if critical risks are DEGRADING
    degrading = [
        r["id"] for r in pack["risk_register"]
        if r["drift"] == "DEGRADING"
    ]
    if degrading:
        logger.warning(
            "DEGRADING risks detected: %s — review pack written but exit code 1.",
            ", ".join(degrading),
        )
        return 1

    return 0


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rc   = asyncio.run(_run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
