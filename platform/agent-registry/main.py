"""
Agent Registry — FastAPI service.
Namespace:   i3-agent-mesh
Port:        8200
DB:          $AGENT_REGISTRY_DB_URL (PostgreSQL via asyncpg)

Endpoints:
  GET    /agents                      → list all registered agents
  POST   /agents                      → register a new agent manifest
  GET    /agents/{agent_id}           → get one manifest
  PATCH  /agents/{agent_id}/state     → update lifecycle state (active|suspended|retired)
  GET    /agents/{agent_id}/decisions → paginated decision log for one agent
  POST   /decisions                   → emit a decision log entry (fire-and-forget from agents)
  GET    /healthz                     → liveness probe
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID, uuid4

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from models import AgentManifest, DecisionCreate, AgentStateUpdate
from schemas import (
    AgentStateResponse,
    AgentListResponse,
    AgentDecision,
    DecisionListResponse,
)

# ── Logging ────────────────────────────────────────────────────────────────
log = logging.getLogger("agent-registry")
logging.basicConfig(level=logging.INFO)

# ── Config ─────────────────────────────────────────────────────────────────
DB_URL             = os.environ["AGENT_REGISTRY_DB_URL"]
DEFAULT_TENANT_ID  = os.getenv(
    "DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001"
)
MANIFESTS_DIR      = os.path.join(os.path.dirname(__file__), "manifests")

# ── Connection Pool ────────────────────────────────────────────────────────
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DB_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


# ── Startup: seed manifests from YAML files ────────────────────────────────

async def _seed_manifests(pool: asyncpg.Pool) -> None:
    """Load *.yaml manifest files from the manifests/ directory into the DB."""
    import glob
    import yaml  # pyyaml

    files = glob.glob(os.path.join(MANIFESTS_DIR, "*.yaml"))
    if not files:
        log.warning("No manifest YAML files found in %s", MANIFESTS_DIR)
        return

    async with pool.acquire() as conn:
        for fpath in files:
            try:
                with open(fpath) as f:
                    raw = yaml.safe_load(f)

                # Support both flat manifests and nested (admissions-agent-v1 format)
                m = raw.get("manifest", raw) if isinstance(raw, dict) else raw

                # Enforce HC-3: no tier above L1 at load time
                tier = m.get("autonomy_tier", m.get("autonomy_level", "L1"))
                if tier not in ("L0", "L1"):
                    log.error(
                        "MANIFEST REJECTED %s: autonomy_tier=%s exceeds L1 — HC-3 violation",
                        fpath, tier,
                    )
                    continue

                # IMP-12: read risk_tier (numeric 0–3) and approval_policy
                raw_risk_tier = m.get("risk_tier", 1)
                try:
                    risk_tier = int(raw_risk_tier)
                except (TypeError, ValueError):
                    # Legacy string values: low→1, medium→2, high→3
                    risk_tier = {"low": 1, "medium": 2, "high": 3}.get(
                        str(raw_risk_tier).lower(), 1
                    )
                approval_policy = m.get("approval_policy", "human_required" if risk_tier >= 3 else "auto")

                # Extract allowed_tools: support list[str] and list[dict]
                raw_tools = m.get("allowed_tools", [])
                allowed_tools = [
                    (t["name"] if isinstance(t, dict) else t)
                    for t in raw_tools
                ]

                raw_forbidden = m.get("forbidden_tools", m.get("denied_tools", []))
                forbidden_tools = [
                    (t["name"] if isinstance(t, dict) else t)
                    for t in raw_forbidden
                ]

                await conn.execute(
                    """
                    INSERT INTO agent_registry
                      (tenant_id, agent_id, name, version, autonomy_tier,
                       allowed_tools, forbidden_tools, cost_budget_tokens,
                       guardrail_policy, owner, state, risk_tier, approval_policy)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    ON CONFLICT (agent_id) DO UPDATE SET
                      name              = EXCLUDED.name,
                      version           = EXCLUDED.version,
                      autonomy_tier     = EXCLUDED.autonomy_tier,
                      allowed_tools     = EXCLUDED.allowed_tools,
                      forbidden_tools   = EXCLUDED.forbidden_tools,
                      cost_budget_tokens= EXCLUDED.cost_budget_tokens,
                      guardrail_policy  = EXCLUDED.guardrail_policy,
                      owner             = EXCLUDED.owner,
                      state             = EXCLUDED.state,
                      risk_tier         = EXCLUDED.risk_tier,
                      approval_policy   = EXCLUDED.approval_policy,
                      updated_at        = now()
                    """,
                    UUID(m.get("tenant_id", DEFAULT_TENANT_ID)),
                    m["agent_id"],
                    m.get("name", m.get("agent_id")),
                    m.get("version", "1.0.0"),
                    tier,
                    allowed_tools,
                    forbidden_tools,
                    int(m.get("cost_budget_tokens", 50000)),
                    m.get("guardrail_policy", "lobster-trap-v1"),
                    m.get("owner", "i3-technologies"),
                    m.get("state", "active"),
                    risk_tier,
                    approval_policy,
                )
                log.info(
                    "Seeded manifest: %s (autonomy=%s, risk_tier=%d, approval=%s)",
                    m["agent_id"], tier, risk_tier, approval_policy,
                )
            except Exception as exc:
                log.error("Failed to seed %s: %s", fpath, exc)


# ── App lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    await _seed_manifests(pool)
    log.info("Agent Registry started — manifests seeded")
    yield
    if _pool:
        await _pool.close()
    log.info("Agent Registry shutting down")


app = FastAPI(
    title="i3 Agent Registry",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://engage.i3technologies.co.ke",
        "https://evalos.i3technologies.co.ke",
        "https://pmaas.i3technologies.co.ke",
        "https://admissions.i3technologies.co.ke",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)


# ── Helper: row → AgentManifest ────────────────────────────────────────────

def _row_to_manifest(row: asyncpg.Record) -> AgentManifest:
    return AgentManifest(
        id=row["id"],
        tenant_id=row["tenant_id"],
        agent_id=row["agent_id"],
        name=row["name"],
        version=row["version"],
        autonomy_tier=row["autonomy_tier"],
        allowed_tools=list(row["allowed_tools"] or []),
        forbidden_tools=list(row["forbidden_tools"] or []),
        cost_budget_tokens=row["cost_budget_tokens"],
        guardrail_policy=row["guardrail_policy"],
        owner=row["owner"],
        state=row["state"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_decision(row: asyncpg.Record) -> AgentDecision:
    return AgentDecision(
        id=row["id"],
        tenant_id=row["tenant_id"],
        agent_id=row["agent_id"],
        session_id=row["session_id"],
        autonomy_tier=row["autonomy_tier"],
        model=row["model"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        tools_invoked=list(row["tools_invoked"] or []),
        policy_decision=row["policy_decision"],
        outcome=row["outcome"],
        human_approver=row["human_approver"],
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        timestamp=row["timestamp"],
        metadata=dict(row["metadata"]) if row["metadata"] else None,
    )


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/agents", response_model=AgentListResponse)
async def list_agents():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM agent_registry WHERE state != 'retired' ORDER BY agent_id"
        )
    agents = [_row_to_manifest(r) for r in rows]
    return AgentListResponse(agents=agents, total=len(agents))


@app.post("/agents", response_model=AgentManifest, status_code=201)
async def register_agent(manifest: AgentManifest):
    # HC-3: block any tier > L1
    if manifest.autonomy_tier not in ("L0", "L1"):
        raise HTTPException(
            status_code=422,
            detail=f"autonomy_tier={manifest.autonomy_tier} exceeds L1 ceiling — HC-3",
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO agent_registry
                  (tenant_id, agent_id, name, version, autonomy_tier,
                   allowed_tools, forbidden_tools, cost_budget_tokens,
                   guardrail_policy, owner, state)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                """,
                manifest.tenant_id,
                manifest.agent_id,
                manifest.name,
                manifest.version,
                manifest.autonomy_tier,
                manifest.allowed_tools,
                manifest.forbidden_tools,
                manifest.cost_budget_tokens,
                manifest.guardrail_policy,
                manifest.owner,
                manifest.state,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(409, detail=f"agent_id={manifest.agent_id} already registered")

    row = await _fetch_agent(manifest.agent_id)
    return row


@app.get("/agents/{agent_id}", response_model=AgentManifest)
async def get_agent(agent_id: str):
    row = await _fetch_agent(agent_id)
    if row is None:
        raise HTTPException(404, detail=f"Agent {agent_id} not found")
    return row


@app.patch("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def update_agent_state(agent_id: str, body: AgentStateUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            UPDATE agent_registry
               SET state = $1, updated_at = now()
             WHERE agent_id = $2
            RETURNING agent_id, state
            """,
            body.state,
            agent_id,
        )
    if result is None:
        raise HTTPException(404, detail=f"Agent {agent_id} not found")
    return AgentStateResponse(agent_id=result["agent_id"], state=result["state"])


@app.get("/agents/{agent_id}/decisions", response_model=DecisionListResponse)
async def get_agent_decisions(
    agent_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    offset = (page - 1) * page_size
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT count(*) FROM agent_decision_log WHERE agent_id = $1", agent_id
        )
        rows = await conn.fetch(
            """
            SELECT * FROM agent_decision_log
             WHERE agent_id = $1
             ORDER BY timestamp DESC
             LIMIT $2 OFFSET $3
            """,
            agent_id, page_size, offset,
        )
    decisions = [_row_to_decision(r) for r in rows]
    return DecisionListResponse(
        decisions=decisions,
        total=total,
        page=page,
        page_size=page_size,
    )


@app.post("/decisions", response_model=AgentDecision, status_code=201)
async def emit_decision(body: DecisionCreate):
    # HC-3: block any tier > L1 in decision records
    if body.autonomy_tier not in ("L0", "L1"):
        raise HTTPException(
            status_code=422,
            detail=f"autonomy_tier={body.autonomy_tier} exceeds L1 ceiling — HC-3",
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_decision_log
              (tenant_id, agent_id, session_id, autonomy_tier, model,
               input_tokens, output_tokens, cost_usd, tools_invoked,
               policy_decision, outcome, human_approver,
               correlation_id, causation_id, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            RETURNING *
            """,
            body.tenant_id,
            body.agent_id,
            body.session_id,
            body.autonomy_tier,
            body.model,
            body.input_tokens,
            body.output_tokens,
            body.cost_usd,
            body.tools_invoked,
            body.policy_decision,
            body.outcome,
            body.human_approver,
            body.correlation_id,
            body.causation_id,
            json.dumps(body.metadata) if body.metadata else None,
        )
    return _row_to_decision(row)


@app.get("/healthz")
async def healthz():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as exc:
        raise HTTPException(503, detail=f"DB unreachable: {exc}") from exc


@app.get("/readyz")
async def readyz():
    """Kubernetes readiness probe — confirms DB pool is accepting queries."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT count(*) FROM agent_registry")
        return {"status": "ready", "registered_agents": count}
    except Exception as exc:
        raise HTTPException(503, detail=f"DB unreachable: {exc}") from exc


# ── Internal helper ────────────────────────────────────────────────────────

async def _fetch_agent(agent_id: str) -> AgentManifest | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agent_registry WHERE agent_id = $1", agent_id
        )
    if row is None:
        return None
    return _row_to_manifest(row)
