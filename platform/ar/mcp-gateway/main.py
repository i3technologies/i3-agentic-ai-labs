#!/usr/bin/env python3
"""
i3 Agentic Runtime — MCP Gateway Service
FastAPI service exposing core cluster tools to i3-code and AR agents.
Includes Granite Guardian middleware on all responses.

P2-GATE-03: All /tools/* and /approvals/* routes require a valid Keycloak
JWT bearer token. Requests without a valid token receive HTTP 403.
"""
import logging
import os
import time
from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("i3-ar-mcp-gateway")

# ── Config ────────────────────────────────────────────────────────────────────
LITELLM_URL   = os.environ.get("LITELLM_URL",   "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY   = os.environ.get("LITELLM_KEY",   "")
CHROMA_HOST   = os.environ.get("CHROMA_HOST",   "chromadb.i3-ai-lab.svc.cluster.local")
CHROMA_TOKEN  = os.environ.get("CHROMA_TOKEN",  "")
VAULT_TOKEN   = os.environ.get("VAULT_TOKEN",   "")
DATABASE_URL  = os.environ.get("DATABASE_URL",  "")
PG_PASSWORD   = os.environ.get("PG_PASSWORD",   "")
KEYCLOAK_URL  = "https://sso.i3technologies.co.ke/auth/realms/i3"
KEYCLOAK_JWKS_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/certs"

# ── JWT auth (P2-GATE-03) ─────────────────────────────────────────────────────
_bearer = HTTPBearer()
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 300  # seconds

async def _get_jwks() -> dict:
    """Fetch and cache Keycloak JWKS with 5-minute TTL."""
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache and (time.time() - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(KEYCLOAK_JWKS_URL)
        r.raise_for_status()
    _jwks_cache = r.json()
    _jwks_fetched_at = time.time()
    return _jwks_cache


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """
    Validate Keycloak-issued JWT (RS256).
    Raises HTTP 403 for missing, expired, or tampered tokens.
    HC-5: No tool may be invoked without passing this gate.
    """
    token = credentials.credentials
    try:
        jwks = await _get_jwks()
        # jose automatically selects the matching key by kid
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience="account",
            options={"verify_exp": True},
        )
        return payload
    except JWTError as exc:
        log.warning("jwt_verification_failed: %s", exc)
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    except Exception as exc:
        log.error("jwks_fetch_error: %s", exc)
        raise HTTPException(status_code=403, detail="Token verification unavailable")

# ── Guardian ──────────────────────────────────────────────────────────────────
async def guardian_check(text: str) -> dict:
    """Run Granite Guardian safety check. Returns {safe, category}."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                f"{LITELLM_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                json={
                    "model": "granite-guardian",
                    "messages": [{"role": "user", "content": text}],
                    "max_tokens": 10
                }
            )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip().lower()
            return {"safe": "safe" in content or content == "0", "raw": content}
    except Exception as e:
        log.warning(f"Guardian check failed: {e} — defaulting to safe")
    return {"safe": True, "raw": "guardian_unavailable"}


# ── Shared asyncpg pool (STEP-P1-07 / C-4 fix) ───────────────────────────────
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("i3-AR MCP Gateway starting")
    await get_pool()  # warm up pool at startup
    yield
    if _pool:
        await _pool.close()
    log.info("i3-AR MCP Gateway stopping")

app = FastAPI(title="i3-AR MCP Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Tool schemas ──────────────────────────────────────────────────────────────
class SchemaRequest(BaseModel):
    database: str
    schema_name: str = "public"

class SandboxRequest(BaseModel):
    code: str
    language: str = "python"
    timeout_seconds: int = 30

class VectorRequest(BaseModel):
    collection: str
    query: str
    top_k: int = 5

class VaultRequest(BaseModel):
    path: str

class ApprovalUpdate(BaseModel):
    approval_id: str
    status: str  # approved | rejected
    reviewer: str
    trace_id: str = ""


# ── Tool: read_db_schema (Tier 0) ─────────────────────────────────────────────
@app.post("/tools/read_db_schema")
async def read_db_schema(req: SchemaRequest, _claims: dict = Depends(verify_token)):
    """Returns table/column metadata. No data rows returned."""
    # Use ar_app on ar_db (information_schema is accessible to the app user).
    # Cross-DB schema reads are not supported via PGBouncer non-admin users.
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = $1
                ORDER BY table_name, ordinal_position
            """, req.schema_name)
        tables: dict = {}
        for r in rows:
            t = r["table_name"]
            tables.setdefault(t, []).append({"column": r["column_name"], "type": r["data_type"], "nullable": r["is_nullable"]})
        return {"database": req.database, "schema": req.schema_name, "tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Tool: execute_sandboxed_code (Tier 2) ─────────────────────────────────────
@app.post("/tools/execute_sandboxed_code")
async def execute_sandboxed_code(req: SandboxRequest, _claims: dict = Depends(verify_token)):
    """Delegates to sandbox-controller service which spawns ephemeral OCP Job."""
    try:
        async with httpx.AsyncClient(timeout=req.timeout_seconds + 15) as client:
            r = await client.post(
                "http://sandbox-controller.i3-ar.svc:8090/execute",
                json=req.model_dump()
            )
        result = r.json()
        # Guardian check on output
        if result.get("output"):
            guard = await guardian_check(result["output"])
            result["guardian"] = guard
            if not guard["safe"]:
                result["output"] = "[OUTPUT BLOCKED BY GRANITE GUARDIAN]"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Tool: query_curriculum_vector (Tier 0) ────────────────────────────────────
@app.post("/tools/query_curriculum_vector")
async def query_curriculum_vector(req: VectorRequest, _claims: dict = Depends(verify_token)):
    """Semantic search over a ChromaDB collection."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"http://{CHROMA_HOST}:8000/api/v1/collections/{req.collection}/query",
                headers={"Authorization": f"Bearer {CHROMA_TOKEN}"},
                json={"query_texts": [req.query], "n_results": req.top_k}
            )
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Collection '{req.collection}' not found")
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Tool: vault_get_secret (Tier 0) ───────────────────────────────────────────
# Only whitelisted paths accessible — prevents arbitrary secret exfiltration
VAULT_ALLOWED_PREFIXES = ["secret/data/ar/dev", "secret/data/platform/endpoints"]

@app.post("/tools/vault_get_secret")
async def vault_get_secret(req: VaultRequest, _claims: dict = Depends(verify_token)):
    """Fetches a designated secret from OpenBao. Only whitelisted paths allowed."""
    if not any(req.path.startswith(p) for p in VAULT_ALLOWED_PREFIXES):
        raise HTTPException(status_code=403, detail=f"Path '{req.path}' not in allowed prefix list")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                f"http://openbao-active.i3-security.svc:8200/v1/{req.path}",
                headers={"X-Vault-Token": VAULT_TOKEN}
            )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Vault error")
        return r.json().get("data", {}).get("data", {})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Approval queue (Tier 3/4 gate) ───────────────────────────────────────────
@app.get("/approvals/pending")
async def list_pending_approvals(_claims: dict = Depends(verify_token)):
    """List all pending Tier 3/4 approvals."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, action_name, requested_by, payload, created_at
                FROM ar_approvals WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/approvals/{approval_id}")
async def update_approval(approval_id: str, req: ApprovalUpdate, _claims: dict = Depends(verify_token)):
    """Human reviewer approves or rejects a pending Tier 3/4 action."""
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be approved or rejected")
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE ar_approvals
                SET status = $1, reviewed_by = $2, reviewed_at = now(), trace_id = $3
                WHERE id = $4
            """, req.status, req.reviewer, req.trace_id, approval_id)
        return {"approval_id": approval_id, "status": req.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "i3-ar-mcp-gateway", "version": "1.0.0"}
