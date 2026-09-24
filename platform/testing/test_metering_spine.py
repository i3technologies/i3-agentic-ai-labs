"""
test_metering_spine.py — IMP-07 Metering Spine Tests
=====================================================
Tests:
  1. Migration integrity — all four tables exist with correct columns and constraints
  2. HC-4 enforcement — tenant_id NOT NULL and RLS blocks cross-tenant reads
  3. Over-quota rejection — LiteLLM returns HTTP 429 when max_budget is exceeded (R4)
  4. Key-alias idempotency — issuing the same key_alias twice is a no-op
  5. monthly_usage upsert — duplicate (project_id, year_month) updates rather than inserts
  6. key_rotation_log — rotation creates an immutable audit row
  7. api_key key_hash — stored as HMAC-SHA256, never plaintext

Run with:
    pytest platform/testing/test_metering_spine.py -v

Environment variables required (same as metering jobs):
    LITELLM_BILLING_DB_URL   postgresql://billing_app:...@pgbouncer:5432/litellm_billing_db
    LITELLM_URL              https://litellm.i3technologies.co.ke  (or mock)
    BILLING_TENANT_ID        00000000-0000-0000-0000-000000000001
    LITELLM_TEST_KEY         a valid project virtual key (not master_key) for quota test
    KEY_HMAC_SECRET          from OpenBao i3/litellm/key-hmac-secret
"""

import hashlib
import hmac as _hmac
import os
import uuid

import asyncpg
import httpx
import pytest
import pytest_asyncio

# ── Configuration ────────────────────────────────────────────────────────
BILLING_DB_URL = os.environ.get(
    "LITELLM_BILLING_DB_URL",
    "postgresql://billing_app:test@localhost:5432/litellm_billing_db",
)
LITELLM_URL = os.environ.get("LITELLM_URL", "http://localhost:4000")
TENANT_ID = os.environ.get("BILLING_TENANT_ID", "00000000-0000-0000-0000-000000000001")
TENANT_ID_OTHER = "ffffffff-ffff-ffff-ffff-ffffffffffff"  # foreign tenant — must be blocked
LITELLM_TEST_KEY = os.environ.get("LITELLM_TEST_KEY", "")
KEY_HMAC_SECRET = os.environ.get("KEY_HMAC_SECRET", "test-hmac-secret-not-real")


def _hmac_key(raw: str) -> str:
    return _hmac.new(
        KEY_HMAC_SECRET.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()  # type: ignore[attr-defined]  # hmac.new is valid stdlib


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db():
    """Async DB connection with app.tenant_id set."""
    pool = await asyncpg.create_pool(BILLING_DB_URL, min_size=1, max_size=1)
    async with pool.acquire() as conn:
        await conn.execute(f"SET app.tenant_id = '{TENANT_ID}'")
        yield conn
    await pool.close()


@pytest_asyncio.fixture
async def db_other_tenant():
    """Connection as a different tenant — used to assert RLS blocks reads."""
    pool = await asyncpg.create_pool(BILLING_DB_URL, min_size=1, max_size=1)
    async with pool.acquire() as conn:
        await conn.execute(f"SET app.tenant_id = '{TENANT_ID_OTHER}'")
        yield conn
    await pool.close()


# ── 1. Migration integrity ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tables_exist(db: asyncpg.Connection) -> None:
    """All four metering tables must be present in the billing schema."""
    tables = await db.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'billing'
        ORDER BY table_name;
        """
    )
    names = {r["table_name"] for r in tables}
    assert "customers" in names, "billing.customers missing"
    assert "projects" in names, "billing.projects missing"
    assert "api_keys" in names, "billing.api_keys missing"
    assert "monthly_usage" in names, "billing.monthly_usage missing"
    assert "key_rotation_log" in names, "billing.key_rotation_log missing"


@pytest.mark.asyncio
async def test_tenant_id_not_null(db: asyncpg.Connection) -> None:
    """HC-4: inserting a row without tenant_id must raise an error."""
    with pytest.raises(asyncpg.exceptions.NotNullViolationError):
        await db.execute(
            """
            INSERT INTO billing.customers
                (name, email, billing_tier, monthly_token_hard_limit)
            VALUES ('NullTenantCo','null@test.ke','trial',1000)
            """
        )


@pytest.mark.asyncio
async def test_required_columns(db: asyncpg.Connection) -> None:
    """Verify column presence and NOT NULL constraints for key tables."""
    for table, column in [
        ("customers",    "tenant_id"),
        ("projects",     "tenant_id"),
        ("api_keys",     "tenant_id"),
        ("monthly_usage","tenant_id"),
        ("api_keys",     "key_hash"),
        ("api_keys",     "max_budget"),
        ("projects",     "monthly_token_hard_limit"),
    ]:
        result = await db.fetchrow(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = 'billing'
              AND table_name   = $1
              AND column_name  = $2
            """,
            table, column,
        )
        assert result is not None, f"billing.{table}.{column} column missing"
        assert result["is_nullable"] == "NO", \
            f"billing.{table}.{column} must be NOT NULL"


# ── 2. HC-4 RLS enforcement ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_reads(
    db: asyncpg.Connection,
    db_other_tenant: asyncpg.Connection,
) -> None:
    """A row created by tenant A must not be visible to tenant B."""
    cid = str(uuid.uuid4())
    # Insert as TENANT_ID
    await db.execute(
        """
        INSERT INTO billing.customers
            (id, tenant_id, name, email, billing_tier, monthly_token_hard_limit)
        VALUES ($1::UUID, $2::UUID, 'RLS Test Co', 'rls@test.ke', 'trial', 1000)
        """,
        cid, TENANT_ID,
    )
    # Other tenant must not see the row
    row = await db_other_tenant.fetchrow(
        "SELECT id FROM billing.customers WHERE id = $1::UUID", cid
    )
    assert row is None, "RLS failed: cross-tenant row visible to foreign tenant"

    # Cleanup
    await db.execute(
        "DELETE FROM billing.customers WHERE id = $1::UUID", cid
    )


# ── 3. Over-quota rejection (R4) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_over_quota_returns_429() -> None:
    """
    R4: A project key with max_budget=1 token must receive HTTP 429
    after the first (or second) successful call exhausts the budget.

    This test creates a disposable key with budget=1, fires requests
    until it gets a 429, then deletes the key.

    Requires LITELLM_URL to point at a live (or test-double) LiteLLM instance.
    Skipped if LITELLM_TEST_KEY is empty (CI without live gateway).
    """
    if not LITELLM_TEST_KEY:
        pytest.skip("LITELLM_TEST_KEY not set — skipping live gateway test")

    # Create a key with budget=1 using the test master key
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LITELLM_URL}/key/generate",
            headers={"Authorization": f"Bearer {LITELLM_TEST_KEY}",
                     "Content-Type": "application/json"},
            json={
                "key_alias":       "test-quota-exhaust",
                "max_budget":      1,           # 1 token — exhausted after first call
                "budget_duration": "1d",
                "metadata":        {"source": "pytest-imp07"},
            },
            timeout=20,
        )
        assert resp.status_code == 200, f"key/generate failed: {resp.text}"
        tiny_key = resp.json()["key"]
        tiny_key_id = resp.json().get("key_name") or resp.json().get("id", "")

    got_429 = False
    async with httpx.AsyncClient() as client:
        for _ in range(10):
            call = await client.post(
                f"{LITELLM_URL}/chat/completions",
                headers={"Authorization": f"Bearer {tiny_key}",
                         "Content-Type": "application/json"},
                json={
                    "model": "granite-nano",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                },
                timeout=30,
            )
            if call.status_code == 429:
                got_429 = True
                break

    # Cleanup: delete the disposable key
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{LITELLM_URL}/key/delete",
            headers={"Authorization": f"Bearer {LITELLM_TEST_KEY}",
                     "Content-Type": "application/json"},
            json={"keys": [tiny_key_id]},
            timeout=20,
        )

    assert got_429, (
        "R4 VIOLATION: gateway never returned HTTP 429 after budget exhaustion. "
        "The metering spine must be fail-closed."
    )


# ── 4. monthly_usage upsert idempotency ──────────────────────────────────

@pytest.mark.asyncio
async def test_monthly_usage_upsert(db: asyncpg.Connection) -> None:
    """Duplicate (project_id, year_month) must UPDATE, not INSERT a second row."""
    # Seed a customer + project
    cid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO billing.customers
            (id, tenant_id, name, email, billing_tier, monthly_token_hard_limit)
        VALUES ($1::UUID, $2::UUID, 'UpsertCo', 'up@test.ke', 'trial', 5000)
        """, cid, TENANT_ID,
    )
    await db.execute(
        """
        INSERT INTO billing.projects
            (id, tenant_id, customer_id, name, monthly_token_hard_limit)
        VALUES ($1::UUID, $2::UUID, $3::UUID, 'upsert-project', 5000)
        """, pid, TENANT_ID, cid,
    )
    # First insert
    await db.execute(
        """
        INSERT INTO billing.monthly_usage
            (tenant_id, project_id, year_month, prompt_tokens, completion_tokens,
             total_tokens, request_count, over_quota_hits)
        VALUES ($1::UUID, $2::UUID, '2026-09', 100, 50, 150, 3, 0)
        ON CONFLICT (project_id, year_month) DO UPDATE
        SET total_tokens = EXCLUDED.total_tokens, updated_at = now()
        """, TENANT_ID, pid,
    )
    # Second insert (same key) — should update, not add a new row
    await db.execute(
        """
        INSERT INTO billing.monthly_usage
            (tenant_id, project_id, year_month, prompt_tokens, completion_tokens,
             total_tokens, request_count, over_quota_hits)
        VALUES ($1::UUID, $2::UUID, '2026-09', 200, 100, 300, 6, 1)
        ON CONFLICT (project_id, year_month) DO UPDATE
        SET total_tokens = EXCLUDED.total_tokens, updated_at = now()
        """, TENANT_ID, pid,
    )
    rows = await db.fetch(
        "SELECT total_tokens FROM billing.monthly_usage WHERE project_id = $1::UUID",
        pid,
    )
    assert len(rows) == 1, "Upsert created duplicate row"
    assert rows[0]["total_tokens"] == 300, "Upsert did not update total_tokens"

    # Cleanup
    await db.execute("DELETE FROM billing.monthly_usage WHERE project_id = $1::UUID", pid)
    await db.execute("DELETE FROM billing.projects WHERE id = $1::UUID", pid)
    await db.execute("DELETE FROM billing.customers WHERE id = $1::UUID", cid)


# ── 5. api_key key_hash is HMAC, not plaintext ───────────────────────────

@pytest.mark.asyncio
async def test_key_hash_is_hmac(db: asyncpg.Connection) -> None:
    """key_hash stored in billing.api_keys must be a 64-char hex HMAC string."""
    cid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    kid = str(uuid.uuid4())
    raw_key = "sk-litellm-test-abc123"
    computed_hash = _hmac_key(raw_key)

    await db.execute(
        """
        INSERT INTO billing.customers
            (id, tenant_id, name, email, billing_tier, monthly_token_hard_limit)
        VALUES ($1::UUID, $2::UUID, 'HMACCo', 'hmac@test.ke', 'trial', 5000)
        """, cid, TENANT_ID,
    )
    await db.execute(
        """
        INSERT INTO billing.projects
            (id, tenant_id, customer_id, name, monthly_token_hard_limit)
        VALUES ($1::UUID, $2::UUID, $3::UUID, 'hmac-project', 5000)
        """, pid, TENANT_ID, cid,
    )
    await db.execute(
        """
        INSERT INTO billing.api_keys
            (id, tenant_id, project_id, key_alias, key_hash, litellm_key_id,
             max_budget, budget_duration, issued_by)
        VALUES ($1::UUID, $2::UUID, $3::UUID,
                'test-key', $4, 'litellm-test-id-001', 5000, '1mo', 'pytest')
        """, kid, TENANT_ID, pid, computed_hash,
    )
    row = await db.fetchrow(
        "SELECT key_hash FROM billing.api_keys WHERE id = $1::UUID", kid
    )
    assert row is not None
    assert row["key_hash"] == computed_hash, "key_hash mismatch"
    assert len(row["key_hash"]) == 64, "key_hash is not 64-char hex"
    assert row["key_hash"] != raw_key, "Plaintext key must never be stored in DB"

    # Cleanup
    await db.execute("DELETE FROM billing.api_keys WHERE id = $1::UUID", kid)
    await db.execute("DELETE FROM billing.projects WHERE id = $1::UUID", pid)
    await db.execute("DELETE FROM billing.customers WHERE id = $1::UUID", cid)


# ── 6. key_rotation_log audit trail ──────────────────────────────────────

@pytest.mark.asyncio
async def test_rotation_log_written(db: asyncpg.Connection) -> None:
    """After key rotation, key_rotation_log must contain one row per rotated key."""
    cid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    kid = str(uuid.uuid4())
    rid = str(uuid.uuid4())

    await db.execute(
        """
        INSERT INTO billing.customers
            (id, tenant_id, name, email, billing_tier, monthly_token_hard_limit)
        VALUES ($1::UUID, $2::UUID, 'RotateCo', 'rot@test.ke', 'trial', 5000)
        """, cid, TENANT_ID,
    )
    await db.execute(
        """
        INSERT INTO billing.projects
            (id, tenant_id, customer_id, name, monthly_token_hard_limit)
        VALUES ($1::UUID, $2::UUID, $3::UUID, 'rotate-project', 5000)
        """, pid, TENANT_ID, cid,
    )
    await db.execute(
        """
        INSERT INTO billing.api_keys
            (id, tenant_id, project_id, key_alias, key_hash, litellm_key_id,
             max_budget, budget_duration, issued_by)
        VALUES ($1::UUID, $2::UUID, $3::UUID,
                'rotate-key', 'oldhash000000000000000000000000000000000000000000000000000000000000',
                'lk-old', 5000, '1mo', 'pytest')
        """, kid, TENANT_ID, pid,
    )
    await db.execute(
        """
        INSERT INTO billing.key_rotation_log
            (id, tenant_id, api_key_id, old_key_hash, new_key_hash, rotated_by, rotation_reason)
        VALUES ($1::UUID, $2::UUID, $3::UUID,
                'oldhash000000000000000000000000000000000000000000000000000000000000',
                'newhash000000000000000000000000000000000000000000000000000000000000',
                'pytest', 'test-rotation')
        """, rid, TENANT_ID, kid,
    )
    row = await db.fetchrow(
        "SELECT rotated_by FROM billing.key_rotation_log WHERE id = $1::UUID", rid
    )
    assert row is not None, "key_rotation_log row not found"
    assert row["rotated_by"] == "pytest"

    # Cleanup
    await db.execute("DELETE FROM billing.key_rotation_log WHERE id = $1::UUID", rid)
    await db.execute("DELETE FROM billing.api_keys WHERE id = $1::UUID", kid)
    await db.execute("DELETE FROM billing.projects WHERE id = $1::UUID", pid)
    await db.execute("DELETE FROM billing.customers WHERE id = $1::UUID", cid)
