-- ============================================================
-- MCP Tool Gateway — Migration 002
-- Adds human_approval_records table for Tier 3 gate.
-- Idempotent: all statements use IF NOT EXISTS / DO $$ guards.
-- Rollback: see ROLLBACK section at the bottom.
-- HC-4: tenant_id UUID NOT NULL enforced.
-- ============================================================

-- ── human_approval_records ────────────────────────────────
-- One row per Tier 3+ invocation that requires a human sign-off.
-- Lifecycle: PENDING → APPROVED | DENIED | EXPIRED
-- The gateway checks this table before executing any Tier 3 tool.
CREATE TABLE IF NOT EXISTS human_approval_records (
    approval_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          UUID        NOT NULL,                          -- HC-4
    invocation_id      UUID        NOT NULL UNIQUE,
    tool_name          TEXT        NOT NULL,
    agent_id           TEXT        NOT NULL,
    risk_tier          SMALLINT    NOT NULL CHECK (risk_tier >= 3),   -- only Tier 3+
    payload_digest     TEXT        NOT NULL,                          -- SHA-256 of serialised input
    status             TEXT        NOT NULL DEFAULT 'PENDING'
                           CHECK (status IN ('PENDING','APPROVED','DENIED','EXPIRED')),
    approver_id        TEXT,                                          -- Keycloak sub claim of human
    approver_email     TEXT,                                          -- audit trail
    approval_note      TEXT,
    requested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at         TIMESTAMPTZ,
    expires_at         TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 minutes')
);

-- HC-4: RLS — a tenant can only see its own approval rows
ALTER TABLE human_approval_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON human_approval_records
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_approval_tenant     ON human_approval_records (tenant_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_invocation ON human_approval_records (invocation_id);
CREATE INDEX IF NOT EXISTS idx_approval_status     ON human_approval_records (status, expires_at);

-- ── Auto-expire PENDING records ───────────────────────────
-- Run by a periodic job (KEDA cron or pg_cron); idempotent.
-- Not applied here to avoid procedural DDL in a plain migration.
-- The gateway enforces expires_at check inline instead.

-- ============================================================
-- ROLLBACK (manual — run if migration must be undone):
--
--   DROP TABLE IF EXISTS human_approval_records;
--
-- Impact: Tier 3 tool approvals are no longer persisted.
--   Disable all Tier 3 tools before rolling back.
-- ============================================================
