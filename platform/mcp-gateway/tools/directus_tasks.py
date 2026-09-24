"""
MCP Tool: directus.tasks.write — Tier 2 (customer-facing)

Input schema (stage 1 — prepare):
  { role: str, user_id: str, tasks: [OnboardingTask] }

Output (stage 1):
  { requires_confirmation: bool, token: str, task_count: int, preview: [...], summary: str }

Human-in-the-Loop: returns a staged token; caller must confirm via
  POST /tools/directus.tasks.confirm/invoke  { token: str }
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

import httpx
import redis as redis_lib

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.directus.tasks")

DIRECTUS_URL            = os.environ.get("DIRECTUS_URL", "")
DIRECTUS_TOKEN          = os.environ.get("DIRECTUS_TOKEN", "")
N8N_ONBOARDING_WEBHOOK  = os.environ.get("N8N_ONBOARDING_WEBHOOK_URL", "")
REDIS_URL               = os.environ.get("REDIS_URL", "redis://localhost:6379")

_redis = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)

SPEC_PREPARE = McpToolSpec(
    name="directus.tasks.write",
    description="Stage onboarding tasks for human confirmation before writing to Directus CMS.",
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="customer_facing",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=15_000,
    audit_required=True,
)

SPEC_CONFIRM = McpToolSpec(
    name="directus.tasks.confirm",
    description="Execute a staged onboarding task sync to Directus CMS after human approval.",
    version="1.0.0",
    tenant_scope="single",
    read_write="write",
    side_effect_class="customer_facing",
    risk_tier=2,
    rate_limit=20,
    timeout_ms=30_000,
    audit_required=True,
)


async def handle_prepare(payload: dict[str, Any], *, tenant_id: str, db=None) -> dict:
    tasks = payload.get("tasks", [])
    if not tasks:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Task list is empty — nothing to sync")

    token = str(uuid.uuid4())
    _redis.setex(f"mcp:pending:{token}", 300, json.dumps({
        "action":  "onboarding_sync_tasks",
        "payload": payload,
    }))

    preview = [
        {"day": t.get("day"), "title": t.get("title"), "priority": t.get("priority")}
        for t in tasks[:5]
    ]
    role    = payload.get("role", "")
    user_id = payload.get("user_id", "")
    log.info("Onboarding sync staged: %d tasks for %s / %s", len(tasks), role, user_id)
    return {
        "requires_confirmation": True,
        "token":      token,
        "task_count": len(tasks),
        "preview":    preview,
        "summary": (
            f"Sync {len(tasks)} onboarding tasks for role '{role}' (user: {user_id}) "
            f"to Directus CMS. First 5: {', '.join(t.get('title','') for t in tasks[:5])}"
        ),
    }


async def handle_confirm(payload: dict[str, Any], *, tenant_id: str) -> dict:
    token = payload.get("token", "")
    key   = f"mcp:pending:{token}"
    pipe  = _redis.pipeline()
    pipe.get(key)
    pipe.delete(key)
    raw, _ = pipe.execute()
    if not raw:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Token not found or expired")
    entry = json.loads(raw)
    if entry.get("action") != "onboarding_sync_tasks":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Token action mismatch")

    tasks   = entry["payload"]["tasks"]
    role    = entry["payload"]["role"]
    user_id = entry["payload"]["user_id"]

    synced_ids: list[str] = []
    skipped = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for task in tasks:
            if not DIRECTUS_URL or not DIRECTUS_TOKEN:
                log.warning("DIRECTUS_URL/TOKEN not set — skipping CRM write")
                skipped += 1
                continue
            try:
                resp = await client.post(
                    f"{DIRECTUS_URL}/items/onboarding_tasks",
                    json={
                        "role":            role,
                        "user_id":         user_id,
                        "day":             task.get("day"),
                        "title":           task.get("title"),
                        "description":     task.get("description"),
                        "file_paths":      "\n".join(task.get("file_paths", [])),
                        "verified":        task.get("verified", True),
                        "priority":        task.get("priority", "medium"),
                        "estimated_hours": task.get("estimated_hours", 2.0),
                        "historical_ref":  task.get("historical_ref", ""),
                        "confidence":      task.get("confidence", 0.85),
                        "created_at":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    headers={
                        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
                        "Content-Type":  "application/json",
                    },
                )
                if resp.status_code in (200, 201):
                    synced_ids.append(resp.json().get("data", {}).get("id", "unknown"))
                else:
                    log.warning("Directus returned %d for task: %s", resp.status_code, task.get("title"))
                    skipped += 1
            except Exception as exc:
                log.error("Failed to sync task '%s': %s", task.get("title"), exc)
                skipped += 1

        if N8N_ONBOARDING_WEBHOOK and synced_ids:
            try:
                await client.post(
                    N8N_ONBOARDING_WEBHOOK,
                    json={"event": "onboarding_tasks_synced", "role": role,
                          "user_id": user_id, "task_count": len(synced_ids)},
                    timeout=5.0,
                )
            except Exception as exc:
                log.warning("n8n onboarding webhook failed (non-fatal): %s", exc)

    log.info("Onboarding sync complete: %d synced, %d skipped", len(synced_ids), skipped)
    return {
        "success":       True,
        "synced_count":  len(synced_ids),
        "skipped_count": skipped,
        "directus_ids":  synced_ids,
    }


register_tool(SPEC_PREPARE, handle_prepare)
register_tool(SPEC_CONFIRM, handle_confirm)
