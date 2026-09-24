"""
Agent Registry — Pydantic models and SQLAlchemy table definitions.
Namespace: i3-agent-mesh
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Agent Registry models ──────────────────────────────────────────────────

class AgentManifest(BaseModel):
    """Canonical agent descriptor — mirrors the YAML manifest schema."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    agent_id: str
    name: str
    version: str
    autonomy_tier: str = Field(..., pattern=r"^(L0|L1)$")
    allowed_tools: list[str] = []
    forbidden_tools: list[str] = []
    cost_budget_tokens: int = 50000
    guardrail_policy: str = "lobster-trap-v1"
    owner: str
    state: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class AgentStateUpdate(BaseModel):
    state: str = Field(..., pattern=r"^(active|suspended|retired)$")


# ── Decision Log models ────────────────────────────────────────────────────

class AgentDecision(BaseModel):
    """A single structured decision record emitted by an agent after an LLM call."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    agent_id: str
    session_id: Optional[str] = None
    autonomy_tier: str = Field(..., pattern=r"^(L0|L1)$")
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    tools_invoked: list[str] = []
    policy_decision: Optional[str] = "allowed"
    outcome: Optional[str] = "success"
    human_approver: Optional[str] = None
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[dict] = None

    model_config = {"from_attributes": True}


class DecisionCreate(BaseModel):
    """Payload accepted at POST /decisions — no id/timestamp (set server-side)."""
    tenant_id: UUID
    agent_id: str
    session_id: Optional[str] = None
    autonomy_tier: str = Field("L1", pattern=r"^(L0|L1)$")
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    tools_invoked: list[str] = []
    policy_decision: Optional[str] = "allowed"
    outcome: Optional[str] = "success"
    human_approver: Optional[str] = None
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    metadata: Optional[dict] = None
