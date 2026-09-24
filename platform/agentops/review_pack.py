"""
platform/agentops/review_pack.py — AgentOps Weekly Review Pack data collector

Pulls the six core cadence sections from their authoritative stores:

  1. Autonomy rate per agent   — agent-registry decision_log (DB)
  2. Approval-gate latency     — decision_log (human_approver IS NOT NULL)
  3. Spend per tenant vs budget — billing.monthly_usage + billing.projects (DB)
  4. Evaluation-suite trend    — RAGAS gate evidence JSON (S3 / local)
  5. Audit-trail anomalies     — WORM audit manifest + tamper-check output (S3)
  6. Top-5 risk-register items — risk_register.py (in-process, drift detected)

All DB calls use asyncpg connection pools via async context managers (arch standard).
HC-4: every query filters by tenant_id.
HC-6: no raw NIDs or emails are extracted — only HMAC digests and slugs.

Environment variables
---------------------
AGENTOPS_DB_URL          postgresql://…  (agent-registry + billing schema)
AUDIT_S3_BUCKET          S3 bucket name for WORM audit store
AUDIT_S3_ENDPOINT_URL    optional S3-compatible endpoint
AUDIT_S3_REGION          default us-east-1
RAGAS_EVIDENCE_PATH      local path or s3://bucket/key for latest RAGAS JSON
AGENTOPS_TENANT_IDS      comma-separated UUID list — omit for all tenants
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _db_url() -> str:
    v = os.environ.get("AGENTOPS_DB_URL")
    if not v:
        raise EnvironmentError("AGENTOPS_DB_URL not set")
    return v


def _tenant_filter() -> list[str]:
    raw = os.environ.get("AGENTOPS_TENANT_IDS", "")
    return [t.strip() for t in raw.split(",") if t.strip()] if raw else []


def _s3_client():
    kwargs: dict = {}
    ep = os.environ.get("AUDIT_S3_ENDPOINT_URL")
    if ep:
        kwargs["endpoint_url"] = ep
    region = os.environ.get("AUDIT_S3_REGION", "us-east-1")
    return boto3.client("s3", region_name=region, **kwargs)


# ---------------------------------------------------------------------------
# Section 1 — Autonomy rate per agent
# ---------------------------------------------------------------------------

_AUTONOMY_QUERY = """
SELECT
    agent_id,
    COUNT(*)                                                  AS total_decisions,
    COUNT(*) FILTER (WHERE human_approver IS NULL
                       AND outcome = 'success')               AS autonomous_successes,
    COUNT(*) FILTER (WHERE human_approver IS NOT NULL)        AS human_overrides,
    ROUND(
        COUNT(*) FILTER (WHERE human_approver IS NULL AND outcome = 'success')::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                         AS autonomy_rate_pct,
    tenant_id::text
FROM agent_registry.decision_log
WHERE timestamp >= NOW() - INTERVAL '7 days'
  AND ($1::text[] = '{}' OR tenant_id::text = ANY($1))
GROUP BY agent_id, tenant_id
ORDER BY autonomy_rate_pct DESC NULLS LAST;
"""

async def fetch_autonomy_rates(
    pool: asyncpg.Pool,
    tenant_ids: list[str],
) -> list[dict[str, Any]]:
    """Return autonomy rate per agent over the past 7 days."""
    rows = await pool.fetch(_AUTONOMY_QUERY, tenant_ids or [])
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Section 2 — Approval-gate latency
# ---------------------------------------------------------------------------

_LATENCY_QUERY = """
WITH approvals AS (
    SELECT
        agent_id,
        tenant_id::text,
        timestamp                   AS requested_at,
        LEAD(timestamp) OVER (
            PARTITION BY agent_id, session_id
            ORDER BY timestamp
        )                           AS approved_at
    FROM agent_registry.decision_log
    WHERE timestamp >= NOW() - INTERVAL '7 days'
      AND ($1::text[] = '{}' OR tenant_id::text = ANY($1))
      AND human_approver IS NOT NULL
)
SELECT
    agent_id,
    tenant_id,
    COUNT(*)                                           AS approval_count,
    ROUND(AVG(EXTRACT(EPOCH FROM (approved_at - requested_at))), 1)
                                                       AS avg_latency_sec,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
        ORDER BY EXTRACT(EPOCH FROM (approved_at - requested_at))
    ), 1)                                              AS p95_latency_sec
FROM approvals
WHERE approved_at IS NOT NULL
GROUP BY agent_id, tenant_id
ORDER BY avg_latency_sec DESC NULLS LAST;
"""

async def fetch_gate_latency(
    pool: asyncpg.Pool,
    tenant_ids: list[str],
) -> list[dict[str, Any]]:
    """Return approval-gate latency stats per agent over the past 7 days."""
    rows = await pool.fetch(_LATENCY_QUERY, tenant_ids or [])
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Section 3 — Spend per tenant vs budget
# ---------------------------------------------------------------------------

_SPEND_QUERY = """
SELECT
    c.tenant_id::text,
    c.name                          AS tenant_name,
    mu.year_month,
    mu.total_tokens                 AS tokens_used,
    p.monthly_token_hard_limit      AS token_budget,
    ROUND(mu.total_tokens::numeric /
          NULLIF(p.monthly_token_hard_limit, 0) * 100, 1)
                                    AS budget_utilisation_pct,
    mu.over_quota_hits,
    mu.request_count
FROM billing.monthly_usage    mu
JOIN billing.projects         p  ON p.id = mu.project_id
JOIN billing.customers        c  ON c.id = p.customer_id
WHERE mu.year_month = TO_CHAR(NOW(), 'YYYY-MM')
  AND ($1::text[] = '{}' OR c.tenant_id::text = ANY($1))
ORDER BY budget_utilisation_pct DESC NULLS LAST;
"""

async def fetch_spend_vs_budget(
    pool: asyncpg.Pool,
    tenant_ids: list[str],
) -> list[dict[str, Any]]:
    """Return this-month token spend vs hard-limit budget per tenant."""
    rows = await pool.fetch(_SPEND_QUERY, tenant_ids or [])
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Section 4 — Evaluation-suite trend (RAGAS gate evidence)
# ---------------------------------------------------------------------------

def _load_ragas_evidence(path: str) -> dict[str, Any]:
    """
    Load RAGAS gate-evidence JSON from a local path or S3 URI.
    Returns an empty dict if the file cannot be read (treated as no evidence).
    """
    if path.startswith("s3://"):
        rest = path[5:]
        bucket, _, key = rest.partition("/")
        try:
            resp = _s3_client().get_object(Bucket=bucket, Key=key)
            return json.loads(resp["Body"].read())
        except ClientError as exc:
            logger.warning("Could not load RAGAS evidence from S3: %s", exc)
            return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        logger.warning("Could not load RAGAS evidence from %s: %s", path, exc)
        return {}


def fetch_eval_trend(evidence_path: Optional[str] = None) -> dict[str, Any]:
    """
    Return RAGAS metric snapshot and pass/fail status.
    Reads RAGAS_EVIDENCE_PATH env var if evidence_path is None.
    """
    path = evidence_path or os.environ.get(
        "RAGAS_EVIDENCE_PATH",
        "platform/testing/ragas-gate-evidence.json",
    )
    raw = _load_ragas_evidence(path)
    if not raw:
        return {"status": "NO_EVIDENCE", "metrics": {}}

    metrics = {
        "faithfulness":      raw.get("faithfulness"),
        "answer_relevancy":  raw.get("answer_relevancy"),
        "context_precision": raw.get("context_precision"),
    }
    thresholds = {"faithfulness": 0.80, "answer_relevancy": 0.75}
    passing = all(
        metrics.get(k) is not None
        and not math.isnan(float(metrics[k]))
        and float(metrics[k]) >= v
        for k, v in thresholds.items()
    )
    return {
        "status":   raw.get("status", "PASS" if passing else "FAIL"),
        "gate":     raw.get("gate", "unknown"),
        "model":    raw.get("model", "unknown"),
        "n_queries": raw.get("n_queries"),
        "metrics":  metrics,
        "passing":  passing,
    }


# ---------------------------------------------------------------------------
# Section 5 — Audit-trail anomalies
# ---------------------------------------------------------------------------

_ANOMALY_QUERY = """
SELECT
    tenant_slug,
    service,
    action,
    risk_tier,
    outcome,
    COUNT(*)  AS event_count
FROM audit_events_view          -- materialised view over NDJSON / external table
WHERE occurred_at >= NOW() - INTERVAL '7 days'
  AND (outcome = 'FAILURE' OR outcome = 'DENIED' OR risk_tier = 'CRITICAL')
  AND ($1::text[] = '{}' OR tenant_id::text = ANY($1))
GROUP BY tenant_slug, service, action, risk_tier, outcome
ORDER BY event_count DESC
LIMIT 20;
"""

async def fetch_audit_anomalies(
    pool: asyncpg.Pool,
    tenant_ids: list[str],
) -> list[dict[str, Any]]:
    """
    Return top anomalous audit events (FAILURE / DENIED / CRITICAL) this week.

    Falls back to an empty list if the audit_events_view does not exist
    (e.g., when the WORM store is not yet integrated into Postgres).
    """
    try:
        rows = await pool.fetch(_ANOMALY_QUERY, tenant_ids or [])
        return [dict(r) for r in rows]
    except asyncpg.exceptions.UndefinedTableError:
        logger.warning(
            "audit_events_view not found — WORM audit store may not be "
            "connected to Postgres yet. Returning empty anomaly list."
        )
        return []


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------

async def build_pack(
    *,
    pool: Optional[asyncpg.Pool] = None,
    tenant_ids: Optional[list[str]] = None,
    ragas_evidence_path: Optional[str] = None,
    week_label: Optional[str] = None,
) -> dict[str, Any]:
    """
    Assemble the full AgentOps weekly review pack dict.

    If pool is None a temporary pool is created from AGENTOPS_DB_URL.
    week_label defaults to the ISO week string for today.
    """
    from .risk_register import build_risk_register   # local import avoids circular

    _own_pool = pool is None
    if _own_pool:
        pool = await asyncpg.create_pool(_db_url(), min_size=1, max_size=4)

    try:
        effective_tenants = tenant_ids if tenant_ids is not None else _tenant_filter()

        autonomy, latency, spend, anomalies = await _gather(
            fetch_autonomy_rates(pool, effective_tenants),
            fetch_gate_latency(pool, effective_tenants),
            fetch_spend_vs_budget(pool, effective_tenants),
            fetch_audit_anomalies(pool, effective_tenants),
        )

        eval_trend   = fetch_eval_trend(ragas_evidence_path)
        risk_items   = build_risk_register()

        now = datetime.now(tz=timezone.utc)
        return {
            "generated_at":  now.isoformat(),
            "week":          week_label or now.strftime("W%V-%Y"),
            "tenant_scope":  effective_tenants or "all",
            "autonomy_rates":    autonomy,
            "gate_latency":      latency,
            "spend_vs_budget":   spend,
            "eval_trend":        eval_trend,
            "audit_anomalies":   anomalies,
            "risk_register":     risk_items,
        }
    finally:
        if _own_pool:
            await pool.close()


async def _gather(*coros):
    """Run coroutines concurrently, returning results in order."""
    import asyncio
    return await asyncio.gather(*coros)
