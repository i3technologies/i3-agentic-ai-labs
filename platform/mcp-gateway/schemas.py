"""
MCP Tool Gateway — Shared Pydantic schemas.

Every schema here is the canonical single-definition used by:
  • main.py   (route validation)
  • tools/*   (tool spec registration)
  • migrations/001_init.sql (DDL reference)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Tool specification (registry record) ─────────────────────────────────────

class McpToolSpec(BaseModel):
    name: str                                                                  # dotted namespace, e.g. "chroma.search"
    description: str
    version: str = "1.0.0"
    tenant_scope: Literal["single", "all"] = "single"
    read_write: Literal["read", "write", "readwrite"] = "read"
    side_effect_class: Literal[
        "none", "external_read", "external_write", "customer_facing"
    ] = "none"
    risk_tier: Literal[0, 1, 2, 3] = 0                                        # 0=read-only … 3=financial/legal
    rate_limit: int = 60                                                       # requests per minute per tenant
    timeout_ms: int = 10_000
    audit_required: bool = False


# ── HTTP invocation ───────────────────────────────────────────────────────────

class InvokeRequest(BaseModel):
    input: dict[str, Any]


class InvokeResponse(BaseModel):
    output: Any
    invocation_id: str
    duration_ms: int
    # Tier 3 gate: populated when approval is required / pending
    approval_id: str | None = None
    approval_status: Literal["not_required", "pending", "approved"] | None = None


# ── Invocation audit log row ──────────────────────────────────────────────────

class InvocationRecord(BaseModel):
    invocation_id: str
    tool_name: str
    agent_id: str
    tenant_id: str
    correlation_id: str
    risk_tier: int
    duration_ms: int
    outcome: Literal["success", "error", "blocked", "approval_pending"]
    error_detail: str | None = None


# ── Human approval record (Tier 3 gate) ──────────────────────────────────────

class ApprovalRecord(BaseModel):
    """Mirrors the human_approval_records table row."""
    approval_id: str
    tenant_id: str
    invocation_id: str
    tool_name: str
    agent_id: str
    risk_tier: int
    payload_digest: str
    status: Literal["PENDING", "APPROVED", "DENIED", "EXPIRED"]
    approver_id: str | None = None
    approver_email: str | None = None
    approval_note: str | None = None
    requested_at: datetime
    decided_at: datetime | None = None
    expires_at: datetime


class ApprovalDecide(BaseModel):
    """Body for POST /approvals/{approval_id}/decide."""
    status: Literal["APPROVED", "DENIED"]
    note: str | None = None


# ── Agent manifest (fetched from registry) ───────────────────────────────────

class AgentManifest(BaseModel):
    agent_id: str
    allowed_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    cost_budget_tokens: int = 50_000
    autonomy_tier: Literal["L0", "L1"] = "L1"
    tenant_id: str
