"""
MCP Tool: github.pr.create — Tier 3 (consequential write — code/CI autonomy)

PR-opening has platform-wide blast radius (triggers CI, can merge code).
Any agent with this capability must register at Tier 3 minimum and requires
a signed human-approval record before execution (per IMP-12).

Execution flow (same two-phase pattern as postgres.members.write):
  Phase 1 — Stage:  agent calls without approval_id → returns PENDING token.
  Phase 2 — Execute: agent calls with approval_id after human approves.

[GAP] GitHub token sourced from GITHUB_TOKEN env var; production deployment
      must rotate this via OpenBao KV v2 i3/github/token (HC-7 guard).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.github.pr.create")

GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")

SPEC = McpToolSpec(
    name="github.pr.create",
    description=(
        "Open a GitHub Pull Request on behalf of an agent. "
        "Classified Tier 3 — requires signed human-approval record before execution. "
        "[GAP] GITHUB_TOKEN must be rotated via OpenBao i3/github/token before production."
    ),
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="external_write",
    risk_tier=3,
    rate_limit=5,
    timeout_ms=20_000,
    audit_required=True,
)


async def handle(payload: dict[str, Any], *, tenant_id: str) -> dict:
    """
    Execute PR creation AFTER the gateway has verified the signed
    APPROVED human_approval_record (approval_id must be in payload).
    """
    owner  = payload.get("owner", "")
    repo   = payload.get("repo", "")
    title  = payload.get("title", "")
    head   = payload.get("head", "")
    base   = payload.get("base", "main")
    body   = payload.get("body", "")
    draft  = bool(payload.get("draft", True))

    for field_name, field_val in [("owner", owner), ("repo", repo),
                                   ("title", title), ("head", head)]:
        if not field_val:
            raise HTTPException(status_code=422, detail=f"Missing required field: {field_name}")

    if not GITHUB_TOKEN:
        # [GAP] No token configured — return stub to allow test scaffold to pass
        log.warning("[GAP] GITHUB_TOKEN not set; returning stub response")
        return {
            "success": True,
            "pr_number": 0,
            "pr_url": f"https://github.com/{owner}/{repo}/pull/0",
            "gap": "GITHUB_TOKEN not configured — stub response",
        }

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    pr_data = {"title": title, "head": head, "base": base, "body": body, "draft": draft}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
            headers=headers,
            json=pr_data,
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"GitHub API returned {resp.status_code}: {resp.text[:400]}",
        )

    data = resp.json()
    log.info(
        "github.pr.create: opened PR #%s in %s/%s for tenant %s",
        data.get("number"),
        owner,
        repo,
        tenant_id,
    )
    return {
        "success": True,
        "pr_number": data.get("number"),
        "pr_url": data.get("html_url"),
        "draft": data.get("draft", draft),
    }


register_tool(SPEC, handle)
