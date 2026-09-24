"""
MCP Tool: litellm.chat — Tier 1 (low-risk, cost-budgeted)

Input schema:
  { model: str, messages: [{role, content}], max_tokens?: int, temperature?: float }

Output:
  { content: str, model: str, usage: { input_tokens: int, output_tokens: int } }
"""

from __future__ import annotations

import json as _json
import logging
import os
from typing import Any

import httpx

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.litellm.chat")

LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

SPEC = McpToolSpec(
    name="litellm.chat",
    description="LiteLLM proxy chat completion — routes to configured model backend.",
    version="1.0.0",
    tenant_scope="single",
    read_write="read",
    side_effect_class="none",
    risk_tier=1,
    rate_limit=30,
    timeout_ms=120_000,
    audit_required=False,
)


async def handle(payload: dict[str, Any], *, tenant_id: str, db=None) -> dict:
    model       = payload.get("model", "mistral-nemo")
    messages    = payload.get("messages", [])
    max_tokens  = int(payload.get("max_tokens", 2048))
    temperature = float(payload.get("temperature", 0.3))

    if not messages:
        return {"content": "", "model": model, "usage": {"input_tokens": 0, "output_tokens": 0}}

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={
                "Authorization":       f"Bearer {LITELLM_KEY}",
                "x-litellm-max-tokens": str(max_tokens),
                "x-litellm-metadata":   _json.dumps({"tenant_id": tenant_id, "agent_id": "mcp-gateway"}),
            },
            json={
                "model":       model,
                "messages":    messages,
                "max_tokens":  max_tokens,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data    = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage   = data.get("usage", {})

    log.info("litellm.chat: model=%s in=%d out=%d", model,
             usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    return {
        "content": content,
        "model": model,
        "usage": {
            "input_tokens":  usage.get("prompt_tokens",     0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


register_tool(SPEC, handle)
