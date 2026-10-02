"""
MCP Tool: vpcp.ibm_sales_cloud.sync  — Tier 3 (execute-gated, requires human approval)

HC-5 COMPLIANT:
  This tool wraps the direct syncToIbmSalesCloud Temporal activity call
  that was in the original enterprise_architecture_implementation_guide.md.
  
  ORIGINAL VIOLATION (from guide):
    activities.syncToIbmSalesCloud(dealId, customerAccount, estimatedArr)
    ↑ Direct external HTTP call inside Temporal activity — bypasses
      the MCP Gateway entirely. HC-5 BLOCKED.

  FIXED PATTERN (this file):
    Temporal activity calls:
      POST /tools/vpcp.ibm_sales_cloud.sync/invoke
      Headers: X-Agent-Id, X-Tenant-Id, X-Correlation-Id
      Body: { input: { deal_id, customer_account, ... } }
    
    First call  → HTTP 202 { approval_id, approval_status: "pending" }
    Approver    → POST /approvals/{approval_id}/decide { status: "APPROVED" }
    Second call → HTTP 200 { output: { ibm_ref, synced_at, ... } }

  HC-4: tenant_id is enforced on every IBM Sales Cloud push and audit record.
  HC-5: No direct external HTTP call — all execution gated through human approval.

Execution flow (Tier 3 two-phase):
  Phase 1 (agent first call, no approval_id):
    Gateway stages PENDING human_approval_records row.
    Returns HTTP 202 { approval_id, approval_status: "pending" }.
    Temporal workflow suspends via Workflow.await() until approved.

  Phase 2 (after human approves):
    Agent polls GET /approvals/{approval_id} until APPROVED.
    Agent re-invokes with { approval_id: <uuid> } in input.
    Gateway verifies payload digest matches staged record.
    This handler executes the IBM Sales Cloud API call.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.vpcp.ibm_sales_cloud.sync")

# ── IBM Sales Cloud config (injected from OpenBao i3/vpcp/ibm-sales-cloud) ──
IBM_SALES_CLOUD_API_URL = os.environ.get(
    "IBM_SALES_CLOUD_API_URL",
    "https://api.ibm.com/sales/v1",        # placeholder — real URL from OpenBao
)
IBM_SALES_CLOUD_API_KEY_ENV = "IBM_SALES_CLOUD_API_KEY"

SPEC = McpToolSpec(
    name="vpcp.ibm_sales_cloud.sync",
    description=(
        "Synchronise a registered VPCP deal to IBM Sales Cloud "
        "(Americas_BP_Prospecting co-sell record). "
        "Tier 3: requires explicit human commercial-desk approval before "
        "any data is sent to IBM external systems. "
        "HC-5: all external write traffic is gated through this MCP tool — "
        "never called directly from Temporal activities."
    ),
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="external_write",    # state-mutating external system call
    risk_tier=3,                           # Tier 3 = human approval required
    rate_limit=20,                         # 20 IBM Sales Cloud pushes per minute per tenant
    timeout_ms=30_000,                     # IBM Sales Cloud SLA: up to 30 s
    audit_required=True,
)


async def handle(payload: dict[str, Any], *, tenant_id: str, db=None) -> dict:
    """
    Execute IBM Sales Cloud sync AFTER signed APPROVED human_approval_record
    has been verified by the gateway interceptor.

    By the time this handler runs, the gateway has already:
      - Confirmed approval status == 'APPROVED' and not expired
      - Confirmed payload digest matches the staged record
      - Set tenant_id from the X-Tenant-Id header (HC-4)

    This handler only performs the actual outbound IBM API call.

    HC-4: tenant_id verified before any operation.
    HC-5: This is the ONLY code path that calls IBM Sales Cloud.
          The Temporal DealRegistrationWorkflow must NEVER call IBM APIs directly.
    """

    # ── HC-4 guard ────────────────────────────────────────────────────────
    if not tenant_id:
        raise HTTPException(status_code=422, detail="HC-4: tenant_id is required")

    # ── Input validation ─────────────────────────────────────────────────
    deal_id = payload.get("deal_id")
    customer_account = payload.get("customer_account")
    estimated_arr = payload.get("estimated_arr_usd")
    product_family = payload.get("product_family")
    partner_id = payload.get("partner_id")

    if not deal_id or not customer_account:
        raise HTTPException(
            status_code=422,
            detail="deal_id and customer_account are required for IBM Sales Cloud sync",
        )

    # ── Fetch API key from environment (injected from OpenBao) ────────────
    api_key = os.environ.get(IBM_SALES_CLOUD_API_KEY_ENV, "")
    if not api_key:
        log.warning(
            "[GAP] %s not set — returning stub response for integration tests",
            IBM_SALES_CLOUD_API_KEY_ENV,
        )
        # Stub response for pre-production environments
        return {
            "success": True,
            "ibm_sales_cloud_ref": f"STUB-{deal_id[:8].upper()}",
            "synced_at": "stub",
            "tenant_id": tenant_id,
            "gap": (
                f"{IBM_SALES_CLOUD_API_KEY_ENV} not set — "
                "configure via ExternalSecrets from OpenBao i3/vpcp/ibm-sales-cloud"
            ),
        }

    # ── Push to IBM Sales Cloud ──────────────────────────────────────────
    # HC-5: This is the sole, policy-gated execution path to IBM Sales Cloud.
    ibm_payload = {
        "externalId": deal_id,
        "tenantId": tenant_id,                                      # HC-4
        "customerAccount": customer_account,
        "estimatedAnnualRecurringRevenue": estimated_arr or 0,
        "productFamily": product_family or "watsonx",
        "partnerId": partner_id,
        "source": "i3-vpcp",
        "opportunityType": "co-sell",
    }

    try:
        async with httpx.AsyncClient(timeout=28.0) as client:
            resp = await client.post(
                f"{IBM_SALES_CLOUD_API_URL}/opportunities",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-Tenant-Id": tenant_id,
                    "X-Source": "i3-vpcp-mcp-gateway",
                },
                json=ibm_payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException as exc:
        log.error(
            "IBM Sales Cloud timeout for deal=%s tenant=%s: %s",
            deal_id, tenant_id, exc,
        )
        raise HTTPException(
            status_code=504,
            detail="IBM Sales Cloud API timed out — deal not synced. Retry via approval flow.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        log.error(
            "IBM Sales Cloud HTTP %d for deal=%s tenant=%s: %s",
            exc.response.status_code, deal_id, tenant_id, exc.response.text,
        )
        raise HTTPException(
            status_code=502,
            detail=f"IBM Sales Cloud returned {exc.response.status_code} — deal not synced.",
        ) from exc

    ibm_ref = data.get("opportunityId") or data.get("id") or "unknown"
    log.info(
        "vpcp.ibm_sales_cloud.sync: deal=%s synced to IBM ref=%s tenant=%s",
        deal_id, ibm_ref, tenant_id,
    )
    return {
        "success": True,
        "ibm_sales_cloud_ref": ibm_ref,
        "synced_at": data.get("createdAt"),
        "deal_id": deal_id,
        "tenant_id": tenant_id,
    }


register_tool(SPEC, handle)
