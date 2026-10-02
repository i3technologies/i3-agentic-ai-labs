-- =============================================================================
-- IMP-07: LiteLLM Metering Spine — Billing Schema Migration
-- File:    platform/schemas/metering_billing_migration.sql
-- Target:  billing schema, litellm_billing_db PostgreSQL database
--
-- HC-4: tenant_id UUID NOT NULL on every table, RLS policies on all tables.
-- HC-6: api_keys.key_hash stores HMAC-SHA256 (keyed via KEY_HMAC_SECRET from
--        OpenBao i3/litellm/key-hmac-secret), never the raw key or plain SHA-256.
--
-- Apply with:
--   psql -U billing_admin -d litellm_billing_db -f metering_billing_migration.sql
--
-- Idempotent: uses IF NOT EXISTS / CREATE OR REPLACE throughout.
-- =============================================================================

BEGIN;

-- ── Schema ────────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS billing;

-- ── Row-Level Security helper function ───────────────────────────────────────
-- Each connection sets `app.tenant_id` immediately after acquiring from the pool.
-- All RLS policies call this function to resolve the active tenant.

CREATE OR REPLACE FUNCTION billing.current_tenant_id() RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.tenant_id', true)::UUID;
EXCEPTION
    WHEN others THEN
        RAISE EXCEPTION 'app.tenant_id GUC not set — cannot resolve tenant context';
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ── 1. customers ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS billing.customers (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   UUID        NOT NULL,
    name                        TEXT        NOT NULL,
    email                       TEXT        NOT NULL,
    billing_tier                TEXT        NOT NULL DEFAULT 'trial',
                                            -- 'trial' | 'starter' | 'professional' | 'enterprise'
    monthly_token_hard_limit    BIGINT      NOT NULL DEFAULT 100000,
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE billing.customers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS customers_tenant_isolation ON billing.customers;
CREATE POLICY customers_tenant_isolation ON billing.customers
    USING (tenant_id = billing.current_tenant_id());

CREATE INDEX IF NOT EXISTS idx_customers_tenant ON billing.customers(tenant_id);

-- ── 2. projects ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS billing.projects (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   UUID        NOT NULL,
    customer_id                 UUID        NOT NULL REFERENCES billing.customers(id) ON DELETE CASCADE,
    name                        TEXT        NOT NULL,
    monthly_token_hard_limit    BIGINT      NOT NULL DEFAULT 50000,
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE billing.projects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS projects_tenant_isolation ON billing.projects;
CREATE POLICY projects_tenant_isolation ON billing.projects
    USING (tenant_id = billing.current_tenant_id());

CREATE INDEX IF NOT EXISTS idx_projects_tenant     ON billing.projects(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projects_customer   ON billing.projects(customer_id);

-- ── 3. api_keys ──────────────────────────────────────────────────────────────
-- key_hash MUST be HMAC-SHA256(raw_key, KEY_HMAC_SECRET) — never raw SHA-256
-- or the plaintext key.  Enforced by HC-6.

CREATE TABLE IF NOT EXISTS billing.api_keys (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL,
    project_id          UUID        NOT NULL REFERENCES billing.projects(id) ON DELETE CASCADE,
    key_alias           TEXT        NOT NULL,
    key_hash            TEXT        NOT NULL,   -- 64-char lowercase hex HMAC-SHA256
    litellm_key_id      TEXT        NOT NULL,   -- opaque ID returned by LiteLLM /key/generate
    max_budget          BIGINT      NOT NULL,   -- token budget ceiling
    budget_duration     TEXT        NOT NULL DEFAULT '1mo',
    issued_by           TEXT        NOT NULL,
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_api_keys_alias_project UNIQUE (project_id, key_alias)
);

ALTER TABLE billing.api_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS api_keys_tenant_isolation ON billing.api_keys;
CREATE POLICY api_keys_tenant_isolation ON billing.api_keys
    USING (tenant_id = billing.current_tenant_id());

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant    ON billing.api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_project   ON billing.api_keys(project_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash      ON billing.api_keys(key_hash);

-- ── 4. monthly_usage ─────────────────────────────────────────────────────────
-- One row per (project_id, year_month).  LiteLLM callback upserts on every
-- request; the ON CONFLICT clause is the authoritative update path.

CREATE TABLE IF NOT EXISTS billing.monthly_usage (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL,
    project_id          UUID        NOT NULL REFERENCES billing.projects(id) ON DELETE CASCADE,
    year_month          TEXT        NOT NULL,   -- 'YYYY-MM'  e.g. '2026-03'
    prompt_tokens       BIGINT      NOT NULL DEFAULT 0,
    completion_tokens   BIGINT      NOT NULL DEFAULT 0,
    total_tokens        BIGINT      NOT NULL DEFAULT 0,
    request_count       BIGINT      NOT NULL DEFAULT 0,
    over_quota_hits     BIGINT      NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_monthly_usage_project_month UNIQUE (project_id, year_month)
);

ALTER TABLE billing.monthly_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS monthly_usage_tenant_isolation ON billing.monthly_usage;
CREATE POLICY monthly_usage_tenant_isolation ON billing.monthly_usage
    USING (tenant_id = billing.current_tenant_id());

CREATE INDEX IF NOT EXISTS idx_monthly_usage_tenant  ON billing.monthly_usage(tenant_id);
CREATE INDEX IF NOT EXISTS idx_monthly_usage_project ON billing.monthly_usage(project_id, year_month);

-- ── 5. key_rotation_log ──────────────────────────────────────────────────────
-- Immutable audit trail.  No UPDATE or DELETE RLS policy — append-only intent.

CREATE TABLE IF NOT EXISTS billing.key_rotation_log (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL,
    api_key_id          UUID        NOT NULL REFERENCES billing.api_keys(id) ON DELETE CASCADE,
    old_key_hash        TEXT        NOT NULL,   -- 64-char hex HMAC of the superseded key
    new_key_hash        TEXT        NOT NULL,   -- 64-char hex HMAC of the replacement key
    rotated_by          TEXT        NOT NULL,
    rotation_reason     TEXT,
    rotated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE billing.key_rotation_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS key_rotation_log_tenant_isolation ON billing.key_rotation_log;
CREATE POLICY key_rotation_log_tenant_isolation ON billing.key_rotation_log
    USING (tenant_id = billing.current_tenant_id());

CREATE INDEX IF NOT EXISTS idx_rotation_log_tenant  ON billing.key_rotation_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_rotation_log_key     ON billing.key_rotation_log(api_key_id);

-- ── Application-role grant ────────────────────────────────────────────────────
-- billing_app is the runtime role used by LiteLLM / metering workers.
-- Adjust to match your actual PostgreSQL role name.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'billing_app') THEN
        GRANT USAGE ON SCHEMA billing TO billing_app;
        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA billing TO billing_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA billing TO billing_app;
    END IF;
END;
$$;

COMMIT;
