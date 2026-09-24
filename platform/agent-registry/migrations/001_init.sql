-- ============================================================
-- Agent Registry — Database Migration 001
-- Creates agent_registry and agent_decision_log tables.
-- HC-4: tenant_id UUID NOT NULL on all tables.
-- Target DB: ar_db
-- Apply: psql $AGENT_REGISTRY_DB_URL -f 001_init.sql
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── agent_registry ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_registry (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL,
    agent_id            TEXT        NOT NULL UNIQUE,
    name                TEXT        NOT NULL,
    version             TEXT        NOT NULL DEFAULT '1.0.0',
    autonomy_tier       TEXT        NOT NULL CHECK (autonomy_tier IN ('L0','L1')),  -- HC-3
    allowed_tools       TEXT[]      NOT NULL DEFAULT '{}',
    forbidden_tools     TEXT[]      NOT NULL DEFAULT '{}',
    cost_budget_tokens  INTEGER     NOT NULL DEFAULT 50000,
    guardrail_policy    TEXT        NOT NULL DEFAULT 'lobster-trap-v1',
    owner               TEXT        NOT NULL DEFAULT 'i3-technologies',
    state               TEXT        NOT NULL DEFAULT 'active'
                            CHECK (state IN ('active','suspended','retired')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_tenant
    ON agent_registry (tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_registry_state
    ON agent_registry (state);

-- ── agent_decision_log ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_decision_log (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID        NOT NULL,
    agent_id         TEXT        NOT NULL,
    session_id       TEXT,
    autonomy_tier    TEXT        NOT NULL CHECK (autonomy_tier IN ('L0','L1')),
    model            TEXT,
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    cost_usd         NUMERIC(10,6),
    tools_invoked    TEXT[]      NOT NULL DEFAULT '{}',
    policy_decision  TEXT        NOT NULL DEFAULT 'allow',
    outcome          TEXT,
    human_approver   TEXT,
    correlation_id   TEXT,
    causation_id     TEXT,
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata         JSONB
);

CREATE INDEX IF NOT EXISTS idx_decision_log_agent_id
    ON agent_decision_log (agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decision_log_tenant
    ON agent_decision_log (tenant_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decision_log_session
    ON agent_decision_log (session_id);
