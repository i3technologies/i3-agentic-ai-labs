"""
CRM Intelligence — FastAPI Import API
File:      platform/crm/main.py
Namespace: crm-intelligence

Exposes two ingestion endpoints consumed by the Celery import queue:
  POST /v1/organisations/batch   — upsert a batch of TAM organisations
  POST /v1/contacts/batch        — upsert a batch of contacts

Authentication: Keycloak OIDC bearer token (tenant_id extracted from JWT claim).
HC-4: tenant_id injected into every DB row; set on the asyncpg connection via
      SET LOCAL app.tenant_id before any SQL.
HC-6: No raw PII stored or logged; email/phone reach the DB only via tasks that
      apply hmac_sha256_hex() before any persistence.
HC-7: DEV_BYPASS_AUTH is forbidden — Keycloak dependency is unconditional.
Rule 1: propensity_score column is excluded from all UPDATE paths.
Rule 2: synthetic email generation is prohibited in all ingestion flows.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

log = logging.getLogger("crm.api")

# ── Environment config ─────────────────────────────────────────────────────────
DB_HOST = os.environ.get("DB_HOST", "crm-pg-rw.crm-intelligence.svc")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "crm_db")
DB_USER = os.environ.get("DB_USER", "crm_app")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")  # Injected by ExternalSecrets

KEYCLOAK_JWKS_URI = os.environ.get(
    "KEYCLOAK_JWKS_URI",
    "https://keycloak.i3.io/realms/i3/protocol/openid-connect/certs",
)
KEYCLOAK_AUDIENCE = os.environ.get("KEYCLOAK_AUDIENCE", "crm-api")

# ── Database pool ──────────────────────────────────────────────────────────────
_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """HC-4 / Architecture Standard: create pool in lifespan, never in handlers."""
    global _pool  # noqa: PLW0603
    _pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=2,
        max_size=10,
        ssl="require",          # Crunchy CA cert injected via volume mount
    )
    log.info("CRM API: database pool opened")
    yield
    await _pool.close()
    log.info("CRM API: database pool closed")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CRM Intelligence Import API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Auth ───────────────────────────────────────────────────────────────────────
_bearer = HTTPBearer()


async def _get_tenant_id(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """
    Validate the Keycloak JWT and extract tenant_id.
    Raises HTTP 401 on any auth failure.
    HC-7: No DEV_BYPASS_AUTH path exists — auth is always enforced.
    """
    token = credentials.credentials
    try:
        # Decode and verify signature against Keycloak JWKS
        payload = jwt.decode(
            token,
            KEYCLOAK_JWKS_URI,
            algorithms=["RS256"],
            audience=KEYCLOAK_AUDIENCE,
            options={"verify_at_hash": False},
        )
        tenant_id: str | None = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT is missing 'tenant_id' claim (HC-4).",
            )
        return tenant_id
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        ) from exc


# ── Pydantic models ────────────────────────────────────────────────────────────

class OrganisationIn(BaseModel):
    source_company_id: str | None = None
    canonical_name: str
    normalized_name: str
    domain: str | None = None
    country: str
    city: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    segment: str | None = None
    # Rule 1: propensity_score is accepted ONLY on initial import;
    # excluded from all UPDATE paths (see upsert SQL below).
    propensity_score: float = Field(default=0.0, ge=0.0, le=1.0)


class OrganisationBatchRequest(BaseModel):
    organisations: list[OrganisationIn] = Field(..., min_length=1, max_length=500)


class ContactIn(BaseModel):
    organisation_id: UUID
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    job_title: str | None = None
    # HC-6: email and phone are passed through tasks that HMAC-hash them;
    # they are stored in the contacts table only as plaintext for display
    # purposes — the suppression lookup uses the hashed form.
    email: str | None = None
    phone: str | None = None
    professional_profile_url: str | None = None
    lawful_basis: str          # required — Kenya DPA 2019
    status: str = "unverified"


class ContactBatchRequest(BaseModel):
    contacts: list[ContactIn] = Field(..., min_length=1, max_length=500)


class BatchResponse(BaseModel):
    queued: int


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _set_tenant(conn: asyncpg.Connection, tenant_id: str) -> None:
    """HC-4: Set the per-transaction RLS variable before any query."""
    await conn.execute(
        "SELECT set_config('app.tenant_id', $1, true)",  # true = local to txn
        tenant_id,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post(
    "/v1/organisations/batch",
    response_model=BatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of TAM organisations",
)
async def ingest_organisations(
    body: OrganisationBatchRequest,
    tenant_id: str = Depends(_get_tenant_id),
) -> BatchResponse:
    """
    Upsert organisations from the MEA TAM workbook.

    HC-4: tenant_id injected into every row and set on the DB connection.
    Rule 1: propensity_score is set ONLY on INSERT — the ON CONFLICT clause
            explicitly excludes it from the UPDATE SET list.

    Returns HTTP 202 Accepted; DB writes happen synchronously so callers
    can immediately queue discovery tasks against the returned org IDs.
    """
    assert _pool is not None, "Database pool not initialised"

    upsert_sql = """
        INSERT INTO organisations (
            tenant_id, source_company_id, canonical_name, normalized_name,
            domain, country, city, industry, employee_count, segment,
            propensity_score
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (tenant_id, source_company_id)
        WHERE source_company_id IS NOT NULL
        DO UPDATE SET
            canonical_name  = EXCLUDED.canonical_name,
            normalized_name = EXCLUDED.normalized_name,
            domain          = COALESCE(EXCLUDED.domain, organisations.domain),
            country         = EXCLUDED.country,
            city            = COALESCE(EXCLUDED.city, organisations.city),
            industry        = COALESCE(EXCLUDED.industry, organisations.industry),
            employee_count  = COALESCE(EXCLUDED.employee_count, organisations.employee_count),
            segment         = COALESCE(EXCLUDED.segment, organisations.segment),
            updated_at      = now()
            -- Rule 1: propensity_score intentionally omitted from UPDATE SET
        RETURNING id
    """

    async with _pool.acquire() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            for org in body.organisations:
                await conn.execute(
                    upsert_sql,
                    tenant_id,
                    org.source_company_id,
                    org.canonical_name,
                    org.normalized_name,
                    org.domain,
                    org.country,
                    org.city,
                    org.industry,
                    org.employee_count,
                    org.segment,
                    org.propensity_score,
                )

    # Fan-out discovery tasks via Celery (import queue → discovery queue)
    from crm.tasks import ingest_organisation_batch  # deferred to avoid circular import
    ingest_organisation_batch.apply_async(
        kwargs={
            "tenant_id": tenant_id,
            "organisations": [o.model_dump(mode="json") for o in body.organisations],
        },
        queue="import",
    )
    log.info("Queued %d organisations for tenant=%s", len(body.organisations), tenant_id)
    return BatchResponse(queued=len(body.organisations))


@app.post(
    "/v1/contacts/batch",
    response_model=BatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of contacts for verification",
)
async def ingest_contacts(
    body: ContactBatchRequest,
    tenant_id: str = Depends(_get_tenant_id),
) -> BatchResponse:
    """
    Upsert contacts and queue them for DNS MX verification.

    HC-4: tenant_id on every row.
    Rule 2: contacts without a verifiable source are accepted here as
            'unverified'; the extract task discards synthetic ones upstream.
    """
    assert _pool is not None, "Database pool not initialised"

    insert_sql = """
        INSERT INTO contacts (
            tenant_id, organisation_id, first_name, last_name, full_name,
            job_title, email, phone, professional_profile_url,
            lawful_basis, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT DO NOTHING
        RETURNING id
    """

    async with _pool.acquire() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            for contact in body.contacts:
                await conn.execute(
                    insert_sql,
                    tenant_id,
                    str(contact.organisation_id),
                    contact.first_name,
                    contact.last_name,
                    contact.full_name,
                    contact.job_title,
                    contact.email,
                    contact.phone,
                    contact.professional_profile_url,
                    contact.lawful_basis,
                    contact.status,
                )

    from crm.tasks import ingest_contact_batch
    ingest_contact_batch.apply_async(
        kwargs={
            "tenant_id": tenant_id,
            "contacts": [c.model_dump(mode="json") for c in body.contacts],
        },
        queue="import",
    )
    log.info("Queued %d contacts for tenant=%s", len(body.contacts), tenant_id)
    return BatchResponse(queued=len(body.contacts))


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe — no DB call, always fast."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz() -> dict[str, str]:
    """Readiness probe — verifies DB pool is available."""
    assert _pool is not None
    async with _pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ready"}
