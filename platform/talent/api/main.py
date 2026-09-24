#!/usr/bin/env python3
"""
i3 Talent Cloud API — FastAPI
Endpoints: candidates, skills, assessments, jobs, placements, bench, match

Architecture standards (02-architecture-standards.md):
  - asyncpg.create_pool in lifespan (NEVER asyncpg.connect() in handlers)
  - All DB calls use async context managers (pool.acquire())
  - LiteLLM match prompts pass through Lobster Trap (external job descriptions)
"""
import os
import uuid
import logging
import json
import httpx
import asyncpg
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

log = logging.getLogger("talent-api")
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.environ["DATABASE_URL"]
LITELLM_URL  = os.environ.get("LITELLM_URL", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY  = os.environ.get("LITELLM_KEY", "")
EVALOS_URL   = os.environ.get("EVALOS_URL", "http://evalos-web.i3-evalos.svc.cluster.local:3000")

from fastapi.responses import RedirectResponse

# ── Lobster Trap (subset) — guard LLM prompts built from external inputs ──────
# Job descriptions arrive from untrusted callers and are embedded directly in
# the match prompt.  Block the same 12 patterns used by the Python services.
_TRAP_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"system\s+prompt\s+override", re.I),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.I),
    re.compile(r"output\s+all\s+passwords", re.I),
    re.compile(r"reveal\s+internal\s+logic", re.I),
    re.compile(r"bypass\s+safety\s+filter", re.I),
    re.compile(r"act\s+as\s+DAN", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"drop\s+table", re.I),
    re.compile(r"prompt\s+injection", re.I),
    re.compile(r"disregard\s+(all\s+)?previous", re.I),
    re.compile(r"\bexfiltrate\b", re.I),
]


def _lobster_trap(text: str) -> str | None:
    """Return matched pattern string if injection detected, else None."""
    for pattern in _TRAP_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


# ── Pool lifecycle ─────────────────────────────────────────────────────────────
_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
        statement_cache_size=0,
    )
    log.info("asyncpg pool ready (min=2 max=10)")
    yield
    await _pool.close()
    log.info("talent-api shutdown: pool closed")


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "pool not initialised"
    return _pool


app = FastAPI(title="i3 Talent Cloud API", version="1.0.0", lifespan=lifespan)
# CORS is enforced at the Kong API Gateway layer (STEP-P2-07).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.i3technologies.co.ke"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    allow_credentials=True,
)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


# ── Models ────────────────────────────────────────────────────────────────────
class CandidateCreate(BaseModel):
    keycloak_sub: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    source: str = "direct"
    evalos_passport_id: Optional[str] = None

class JobCreate(BaseModel):
    title: str
    client: Optional[str] = None
    description: Optional[str] = None
    skills_req: Optional[dict] = None

class MatchRequest(BaseModel):
    job_id: str
    top_k: int = 5


# ── Candidates ────────────────────────────────────────────────────────────────
@app.post("/api/v1/candidates", status_code=201)
async def create_candidate(req: CandidateCreate):
    """Create or upsert a candidate. Used by SIT placement bridge."""
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                INSERT INTO candidates (keycloak_sub, full_name, email, phone, location, source, evalos_passport_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (keycloak_sub) DO UPDATE
                  SET full_name = EXCLUDED.full_name,
                      email = COALESCE(EXCLUDED.email, candidates.email),
                      updated_at = now()
                RETURNING id, keycloak_sub, full_name, source, bench_status, created_at
            """, req.keycloak_sub, req.full_name, req.email, req.phone,
                 req.location, req.source, req.evalos_passport_id)
            # Auto-create passport record
            await conn.execute("""
                INSERT INTO passports (candidate_id) VALUES ($1)
                ON CONFLICT (candidate_id) DO NOTHING
            """, row["id"])
            return dict(row)


@app.get("/api/v1/candidates/{candidate_id}")
async def get_candidate(candidate_id: str):
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM candidates WHERE id = $1", uuid.UUID(candidate_id))
    if not row:
        raise HTTPException(404, "Candidate not found")
    return dict(row)


@app.get("/api/v1/bench")
async def list_bench(location: Optional[str] = None, skill: Optional[str] = None):
    """Available bench talent — optionally filtered by location or skill."""
    query = "SELECT c.id, c.full_name, c.location, c.source, c.evalos_passport_id FROM candidates c WHERE c.bench_status = 'available'"
    params: list = []
    if location:
        params.append(location)
        query += f" AND c.location ILIKE ${len(params)}"
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


# ── Jobs ──────────────────────────────────────────────────────────────────────
@app.post("/api/v1/jobs", status_code=201)
async def create_job(req: JobCreate):
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO jobs (title, client, description, skills_req)
            VALUES ($1, $2, $3, $4) RETURNING *
        """, req.title, req.client, req.description,
             json.dumps(req.skills_req) if req.skills_req else None)
    return dict(row)


# ── AI Match ──────────────────────────────────────────────────────────────────
@app.post("/api/v1/match")
async def match_candidates(req: MatchRequest):
    """LiteLLM-powered JD-to-bench matching."""
    async with get_pool().acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", uuid.UUID(req.job_id))
        bench = await conn.fetch(
            "SELECT id, full_name, location FROM candidates WHERE bench_status = 'available' LIMIT 50"
        )

    if not job:
        raise HTTPException(404, "Job not found")

    # Lobster Trap: job descriptions come from external callers — screen before
    # embedding in the LLM prompt (02-architecture-standards.md / HC-5).
    for field in (job["title"], job["description"] or "", str(job["skills_req"] or "")):
        hit = _lobster_trap(field)
        if hit:
            log.warning("lobster_trap_blocked job_id=%s pattern=%r", req.job_id, hit)
            raise HTTPException(400, f"Job description rejected: potential injection ({hit})")

    bench_list = "\n".join([
        f"- {r['id']}: {r['full_name']} ({r['location'] or 'unknown'})"
        for r in bench
    ])
    prompt = f"""Job: {job['title']}
Description: {job['description']}
Skills required: {job['skills_req']}

Available bench candidates:
{bench_list}

Return the top {req.top_k} best-matched candidate IDs with a brief reason each. Format: ID | reason"""

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            json={"model": "qwen-fast", "messages": [{"role": "user", "content": prompt}], "max_tokens": 500}
        )
    content = r.json()["choices"][0]["message"]["content"]
    return {"job_id": req.job_id, "matches": content, "model": "qwen-fast", "status": "proposed"}


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "talent-api", "version": "1.0.0"}
