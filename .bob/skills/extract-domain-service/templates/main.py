"""
<service_name> — Domain Service
Namespace: i3-<namespace>

FastAPI bounded-context microservice following i3 DDD standards.
Credentials injected via OpenBao agent sidecar at runtime.
"""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Logging ─────────────────────────────────────────────────────────────────
log = logging.getLogger("<service_name>")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Config ───────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ["DATABASE_URL"]           # Injected by OpenBao — never hardcode
DEFAULT_TENANT_ID = os.getenv(
    "DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001"
)

# ── Lifespan — asyncpg pool (HC-4 compliant) ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    log.info("<service_name> pool ready")
    yield
    await app.state.pool.close()


app = FastAPI(title="<service_name>", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────────────────────
class CreateRequest(BaseModel):
    tenant_id: uuid.UUID = Field(default_factory=lambda: uuid.UUID(DEFAULT_TENANT_ID))
    # TODO: add domain-specific fields here


class ResourceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    # TODO: add domain-specific fields here


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def ready(request: Request) -> dict:
    async with request.app.state.pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ready"}


@app.post("/resources", response_model=ResourceResponse, status_code=201)
async def create_resource(body: CreateRequest, request: Request) -> ResourceResponse:
    resource_id = uuid.uuid4()
    async with request.app.state.pool.acquire() as conn:
        # HC-4: always pass tenant_id
        await conn.execute(
            """
            INSERT INTO resources (id, tenant_id)
            VALUES ($1, $2)
            """,
            resource_id,
            body.tenant_id,
        )
    return ResourceResponse(id=resource_id, tenant_id=body.tenant_id)
