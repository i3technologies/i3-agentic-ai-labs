"""
Agent Registry — HTTP response / request schemas (OpenAPI-facing).
Thin wrappers around the domain models to separate transport from domain.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models import AgentManifest, AgentDecision, DecisionCreate, AgentStateUpdate

__all__ = [
    "AgentManifest",
    "AgentDecision",
    "DecisionCreate",
    "AgentStateUpdate",
    "AgentStateResponse",
    "AgentListResponse",
    "DecisionListResponse",
]


class AgentStateResponse(BaseModel):
    agent_id: str
    state: str


class AgentListResponse(BaseModel):
    agents: list[AgentManifest]
    total: int


class DecisionListResponse(BaseModel):
    decisions: list[AgentDecision]
    total: int
    page: int
    page_size: int
