#!/usr/bin/env python3
"""
metering_etl.py — Nightly ETL: per-customer token usage statements
=================================================================
IMP-07 / PLN-02/PLN-05 — LiteLLM Metering Spine

Runs as a Kubernetes CronJob (schedule: "5 0 * * *" — 00:05 UTC daily).

Workflow
--------
1. Connect to LiteLLM billing DB (litellm_billing_db) and pull per-key
   spend from LiteLLM's internal `LiteLLM_SpendLogs` table for the
   prior calendar month (or yesterday for daily snapshots).
2. Aggregate by project_id → (prompt_tokens, completion_tokens, total_tokens,
   request_count, over_quota_hits).
3. Upsert into billing.monthly_usage (HC-4: tenant_id on every row).
4. Render a JSON statement per customer and upload to object storage
   (S3-compatible — i3 uses MinIO on-cluster):
     s3://i3-billing/statements/<tenant_id>/<customer_id>/<YYYY-MM>.json
5. Write statement_path and etl_run_at back to billing.monthly_usage.

Security
--------
- All credentials sourced from environment variables (injected by OpenBao).
- HC-4: tenant_id propagated through every DB write.
- R4: over_quota_hits counted from HTTP 429 log entries.
- No master_key used; ETL connects directly to litellm_billing_db as
  billing_app role (read-only on LiteLLM spend tables).
"""

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("metering_etl")

# ── Environment variables (injected from OpenBao via CronJob Secret) ──────
BILLING_DB_URL: str = os.environ["LITELLM_BILLING_DB_URL"]
LITELLM_DB_URL: str = os.environ["LITELLM_DB_URL"]       # same DB, litellm schema
TENANT_ID: str = os.environ["BILLING_TENANT_ID"]
S3_ENDPOINT: str = os.environ.get("S3_ENDPOINT", "http://minio.i3-data.svc.cluster.local:9000")
S3_BUCKET: str = os.environ.get("S3_BILLING_BUCKET", "i3-billing")
S3_ACCESS_KEY: str = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY: str = os.environ["S3_SECRET_KEY"]

# ── Which month to process (default: previous calendar month) ─────────────
_today = date.today()
YEAR_MONTH: str = os.environ.get(
    "ETL_YEAR_MONTH",
    f"{_today.replace(day=1) - timedelta(days=1):%Y-%m}",
)

# =============================================================
# 1. Fetch raw spend from LiteLLM's SpendLogs table
# =============================================================
SPEND_QUERY = """
SELECT
    sl.api_key,
    ak.project_id,
    ak.tenant_id,
    SUM(sl.prompt_tokens)      AS prompt_tokens,
    SUM(sl.completion_tokens)  AS completion_tokens,
    SUM(sl.total_tokens)       AS total_tokens,
    COUNT(*)                   AS request_count
FROM "LiteLLM_SpendLogs" sl
JOIN billing.api_keys ak
    ON sl.api_key = ak.litellm_key_id
WHERE to_char(sl.startTime AT TIME ZONE 'UTC', 'YYYY-MM') = $1
  AND ak.tenant_id = $2::UUID
GROUP BY sl.api_key, ak.project_id, ak.tenant_id;
"""

QUOTA_HIT_QUERY = """
SELECT
    ak.project_id,
    COUNT(*) AS over_quota_hits
FROM "LiteLLM_ErrorLogs" el
JOIN billing.api_keys ak
    ON el.api_key = ak.litellm_key_id
WHERE to_char(el.startTime AT TIME ZONE 'UTC', 'YYYY-MM') = $1
  AND el.status_code = 429
  AND ak.tenant_id = $2::UUID
GROUP BY ak.project_id;
"""

CUSTOMER_QUERY = """
SELECT
    p.id          AS project_id,
    p.name        AS project_name,
    c.id          AS customer_id,
    c.name        AS customer_name,
    c.email       AS customer_email,
    p.monthly_token_hard_limit
FROM billing.projects p
JOIN billing.customers c ON c.id = p.customer_id
WHERE p.tenant_id = $1::UUID
  AND p.active = true;
"""

UPSERT_USAGE = """
INSERT INTO billing.monthly_usage
    (tenant_id, project_id, year_month, prompt_tokens, completion_tokens,
     total_tokens, request_count, over_quota_hits, statement_path, etl_run_at)
VALUES
    ($1::UUID, $2::UUID, $3, $4, $5, $6, $7, $8, $9, now())
ON CONFLICT (project_id, year_month)
DO UPDATE SET
    prompt_tokens     = EXCLUDED.prompt_tokens,
    completion_tokens = EXCLUDED.completion_tokens,
    total_tokens      = EXCLUDED.total_tokens,
    request_count     = EXCLUDED.request_count,
    over_quota_hits   = EXCLUDED.over_quota_hits,
    statement_path    = EXCLUDED.statement_path,
    etl_run_at        = now(),
    updated_at        = now();
"""


async def run_etl() -> None:
    log.info(f"ETL start — year_month={YEAR_MONTH} tenant_id={TENANT_ID}")

    # ── Pools ───────────────────────────────────────────────────────────
    billing_pool = await asyncpg.create_pool(
        BILLING_DB_URL,
        min_size=2,
        max_size=5,
        server_settings={"app.tenant_id": TENANT_ID},
        ssl="require",
    )
    litellm_pool = await asyncpg.create_pool(
        LITELLM_DB_URL,
        min_size=2,
        max_size=5,
        server_settings={"app.tenant_id": TENANT_ID},
        ssl="require",
    )

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )

    try:
        await _ensure_bucket(s3)

        # ── Fetch raw spend data from LiteLLM tables ──────────────────
        async with litellm_pool.acquire() as conn:
            raw_spend = await conn.fetch(SPEND_QUERY, YEAR_MONTH, TENANT_ID)
            quota_hits = await conn.fetch(QUOTA_HIT_QUERY, YEAR_MONTH, TENANT_ID)

        # ── Fetch project→customer mapping ─────────────────────────────
        async with billing_pool.acquire() as conn:
            projects = await conn.fetch(CUSTOMER_QUERY, TENANT_ID)

        # Index by project_id
        quota_map: dict[str, int] = {str(r["project_id"]): r["over_quota_hits"]
                                      for r in quota_hits}
        project_map: dict[str, Any] = {str(r["project_id"]): dict(r)
                                        for r in projects}
        spend_by_project: dict[str, dict] = {}
        for row in raw_spend:
            pid = str(row["project_id"])
            spend_by_project[pid] = {
                "prompt_tokens":      row["prompt_tokens"],
                "completion_tokens":  row["completion_tokens"],
                "total_tokens":       row["total_tokens"],
                "request_count":      row["request_count"],
            }

        # ── Group projects by customer ─────────────────────────────────
        customers: dict[str, dict] = {}
        for pid, proj in project_map.items():
            cid = str(proj["customer_id"])
            if cid not in customers:
                customers[cid] = {
                    "customer_id":    cid,
                    "customer_name":  proj["customer_name"],
                    "customer_email": proj["customer_email"],
                    "year_month":     YEAR_MONTH,
                    "tenant_id":      TENANT_ID,
                    "generated_at":   datetime.now(UTC).isoformat(),
                    "projects":       [],
                    "total_tokens":   0,
                    "total_requests": 0,
                }
            spend = spend_by_project.get(pid, {
                "prompt_tokens": 0, "completion_tokens": 0,
                "total_tokens": 0, "request_count": 0,
            })
            pct_used = round(
                spend["total_tokens"] / proj["monthly_token_hard_limit"] * 100, 2
            ) if proj["monthly_token_hard_limit"] else 0.0
            over_quota = quota_map.get(pid, 0)

            customers[cid]["projects"].append({
                "project_id":              pid,
                "project_name":            proj["project_name"],
                "monthly_token_hard_limit":proj["monthly_token_hard_limit"],
                "prompt_tokens":           spend["prompt_tokens"],
                "completion_tokens":       spend["completion_tokens"],
                "total_tokens":            spend["total_tokens"],
                "request_count":           spend["request_count"],
                "over_quota_hits":         over_quota,
                "pct_of_limit_used":       pct_used,
            })
            customers[cid]["total_tokens"]   += spend["total_tokens"]
            customers[cid]["total_requests"] += spend["request_count"]

        # ── Upload one JSON statement per customer; upsert usage rows ──
        for cid, stmt in customers.items():
            s3_key = f"statements/{TENANT_ID}/{cid}/{YEAR_MONTH}.json"
            body = json.dumps(stmt, indent=2, ensure_ascii=False).encode()
            s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=body,
                          ContentType="application/json",
                          ServerSideEncryption="AES256")
            s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
            log.info(f"Uploaded statement: {s3_uri} ({len(body)} bytes)")

            for proj in stmt["projects"]:
                async with billing_pool.acquire() as conn:
                    await conn.execute(
                        UPSERT_USAGE,
                        TENANT_ID,
                        proj["project_id"],
                        YEAR_MONTH,
                        proj["prompt_tokens"],
                        proj["completion_tokens"],
                        proj["total_tokens"],
                        proj["request_count"],
                        proj["over_quota_hits"],
                        s3_uri,
                    )

        log.info(f"ETL complete — {len(customers)} customers, "
                 f"{sum(len(c['projects']) for c in customers.values())} projects")

    finally:
        await billing_pool.close()
        await litellm_pool.close()


async def _ensure_bucket(s3: Any) -> None:
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            s3.create_bucket(Bucket=S3_BUCKET)
            log.info(f"Created bucket: {S3_BUCKET}")
        else:
            raise


if __name__ == "__main__":
    asyncio.run(run_etl())
