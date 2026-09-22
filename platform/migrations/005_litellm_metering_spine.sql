-- =============================================================
-- Migration 005 — LiteLLM Metering Spine (IMP-07 / PLN-02/PLN-05)
-- Database: litellm_billing_db
-- HC-4: tenant_id UUID NOT NULL on every table
-- HC-7: No DEV_BYPASS_AUTH — billing enforces hard budgets, fail-closed
-- R1:   Virtual keys are the ONLY path to the model gateway.
--        master_key is disabled for interactive use.
-- R4:   Over-quota requests receive HTTP 429; the gateway never degrades
--        to an un-metered path.
-- =============================================================
-- Run as: i3admin (SUPERUSER) against PGBouncer on i3-postgres-pgbouncer.i3-data.svc:5432

CREATE DATABASE litellm_billing_db;
\c litellm_billing_db;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";  -- for query auditing

-- billing schema must exist before tables are created
CREATE SCHEMA IF NOT EXISTS billing;

-- =============================================================
-- 1. CUSTOMERS — one row per paying/metered entity
-- =============================================================
CREATE TABLE billing.customers (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID        NOT NULL,
  name            TEXT        NOT NULL,
  email           TEXT        NOT NULL,
  billing_tier    TEXT        NOT NULL DEFAULT 'standard'
                              CHECK (billing_tier IN ('trial','standard','enterprise')),
  monthly_token_hard_limit BIGINT NOT NULL DEFAULT 500000,
  -- Hard limit; LiteLLM key max_budget is also set to this value (R4 dual enforcement)
  currency        TEXT        NOT NULL DEFAULT 'KES',
  active          BOOLEAN     NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE billing.customers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing.customers;
CREATE POLICY tenant_isolation ON billing.customers
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX idx_customers_tenant ON billing.customers (tenant_id, active);

-- =============================================================
-- 2. PROJECTS — a customer can have N projects, each with its own key
-- =============================================================
CREATE TABLE billing.projects (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID        NOT NULL,
  customer_id       UUID        NOT NULL REFERENCES billing.customers(id) ON DELETE CASCADE,
  name              TEXT        NOT NULL,
  description       TEXT,
  monthly_token_hard_limit BIGINT NOT NULL DEFAULT 100000,
  -- mirrors LiteLLM virtual key max_budget (R1/R4 dual enforcement)
  budget_duration   TEXT        NOT NULL DEFAULT '1mo'
                                CHECK (budget_duration IN ('1d','7d','1mo')),
  active            BOOLEAN     NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (customer_id, name)
);

ALTER TABLE billing.projects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing.projects;
CREATE POLICY tenant_isolation ON billing.projects
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX idx_projects_tenant_customer ON billing.projects (tenant_id, customer_id);
CREATE INDEX idx_projects_active ON billing.projects (active, customer_id);

-- =============================================================
-- 3. API_KEYS — tracks every virtual key issued to a project
-- =============================================================
-- R1: master_key is NEVER stored here; it exists only in OpenBao break-glass path.
-- key_hash is HMAC-SHA256(raw_key, KEY_HMAC_SECRET) — never the plaintext key.
CREATE TABLE billing.api_keys (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID        NOT NULL,
  project_id      UUID        NOT NULL REFERENCES billing.projects(id) ON DELETE CASCADE,
  key_alias       TEXT        NOT NULL,          -- human label e.g. "evalos-study-coach-v2"
  key_hash        TEXT        NOT NULL UNIQUE,   -- HMAC-SHA256(raw_key, KEY_HMAC_SECRET)
  litellm_key_id  TEXT        NOT NULL UNIQUE,   -- LiteLLM internal key id from /key/generate
  max_budget      BIGINT      NOT NULL,          -- token ceiling (R4 — hard, fail-closed)
  budget_duration TEXT        NOT NULL DEFAULT '1mo',
  status          TEXT        NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active','rotated','revoked')),
  rotated_at      TIMESTAMPTZ,
  expires_at      TIMESTAMPTZ,
  issued_by       TEXT        NOT NULL,          -- keycloak_sub of the operator who issued it
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE billing.api_keys ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing.api_keys;
CREATE POLICY tenant_isolation ON billing.api_keys
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX idx_api_keys_tenant_project ON billing.api_keys (tenant_id, project_id);
CREATE INDEX idx_api_keys_status ON billing.api_keys (status, project_id);

-- =============================================================
-- 4. MONTHLY_USAGE — rolling aggregation of token consumption
-- =============================================================
-- Populated by the nightly ETL (metering_etl.py).
-- One row per (project, year_month).
CREATE TABLE billing.monthly_usage (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID        NOT NULL,
  project_id      UUID        NOT NULL REFERENCES billing.projects(id) ON DELETE CASCADE,
  year_month      TEXT        NOT NULL,          -- "2026-09"  (ISO YYYY-MM)
  prompt_tokens   BIGINT      NOT NULL DEFAULT 0,
  completion_tokens BIGINT    NOT NULL DEFAULT 0,
  total_tokens    BIGINT      NOT NULL DEFAULT 0,
  request_count   BIGINT      NOT NULL DEFAULT 0,
  over_quota_hits BIGINT      NOT NULL DEFAULT 0,
  statement_path  TEXT,                          -- object storage URI after ETL upload
  etl_run_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, year_month)
);

ALTER TABLE billing.monthly_usage ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing.monthly_usage;
CREATE POLICY tenant_isolation ON billing.monthly_usage
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX idx_monthly_usage_tenant ON billing.monthly_usage (tenant_id, year_month DESC);
CREATE INDEX idx_monthly_usage_project ON billing.monthly_usage (project_id, year_month DESC);

-- =============================================================
-- 5. KEY_ROTATION_LOG — immutable audit trail for R1 compliance
-- =============================================================
CREATE TABLE billing.key_rotation_log (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID        NOT NULL,
  api_key_id      UUID        NOT NULL REFERENCES billing.api_keys(id),
  old_key_hash    TEXT        NOT NULL,
  new_key_hash    TEXT        NOT NULL,
  rotated_by      TEXT        NOT NULL,          -- keycloak_sub
  rotation_reason TEXT,
  rotated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE billing.key_rotation_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing.key_rotation_log;
CREATE POLICY tenant_isolation ON billing.key_rotation_log
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX idx_key_rotation_log_tenant ON billing.key_rotation_log (tenant_id, rotated_at DESC);

-- =============================================================
-- 6. APP USER + GRANTS
-- =============================================================
CREATE USER billing_app WITH PASSWORD 'REPLACE_BILLING_APP_PASSWORD';
GRANT USAGE ON SCHEMA billing TO billing_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA billing TO billing_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA billing TO billing_app;

-- ETL job gets a read-only grant on the LiteLLM DB spend view
-- (see metering_etl.py — it connects to the LiteLLM DB separately)

-- =============================================================
-- 7. TRIGGER: updated_at maintenance
-- =============================================================
CREATE OR REPLACE FUNCTION billing.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER trg_customers_updated_at BEFORE UPDATE ON billing.customers
  FOR EACH ROW EXECUTE FUNCTION billing.set_updated_at();
CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON billing.projects
  FOR EACH ROW EXECUTE FUNCTION billing.set_updated_at();
CREATE TRIGGER trg_api_keys_updated_at BEFORE UPDATE ON billing.api_keys
  FOR EACH ROW EXECUTE FUNCTION billing.set_updated_at();
CREATE TRIGGER trg_monthly_usage_updated_at BEFORE UPDATE ON billing.monthly_usage
  FOR EACH ROW EXECUTE FUNCTION billing.set_updated_at();
