-- ============================================================
-- Migration: V9__audit_worm_index.sql
-- Platform:  i3 AI Platform — WORM audit pipeline (IMP-09)
-- Constraint: HC-4 — tenant_id UUID NOT NULL on every table
--
-- Creates the audit_events table used as a local hot-tier index
-- for fast query access before the cold-tier S3 WORM store.
-- The S3 objects are the authoritative record; this table enables
-- sub-second lookups by tenant, actor, and date without reading
-- compressed S3 objects.
--
-- Run with Flyway: flyway -url=jdbc:postgresql://... migrate
-- Run manually:   psql $DATABASE_URL -f V9__audit_worm_index.sql
--
-- RLS pattern: same as V1__baseline_tenant_rls.sql
--   SET LOCAL app.tenant_id = '<uuid>' before every query.
-- ============================================================

-- ── audit_events: hot-tier index (local PostgreSQL) ──────────────────────────
-- HC-4: tenant_id UUID NOT NULL enforced by NOT NULL constraint + RLS policy.
-- HC-6: actor_id stores only the HMAC-SHA256 hex digest, never a raw NID.
--       Any INSERT with actor_id that is not 64 lower-case hex chars is
--       rejected by the check constraint.

CREATE TABLE IF NOT EXISTS audit_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID        NOT NULL UNIQUE,
    occurred_at     TIMESTAMPTZ NOT NULL,

    -- HC-4: tenant isolation
    tenant_id       UUID        NOT NULL,
    tenant_slug     TEXT        NOT NULL CHECK (length(tenant_slug) BETWEEN 1 AND 64),

    -- HC-6: actor is a keyed HMAC-SHA256 hex digest, never a raw identifier
    actor_id        CHAR(64)    NOT NULL
                    CHECK (actor_id ~ '^[0-9a-f]{64}$'),
    actor_role      TEXT        NOT NULL CHECK (length(actor_role) <= 128),

    -- Operation
    service         TEXT        NOT NULL CHECK (length(service) <= 64),
    action          TEXT        NOT NULL CHECK (length(action) <= 128),
    resource_type   TEXT        NOT NULL CHECK (length(resource_type) <= 64),
    resource_id     TEXT        NOT NULL CHECK (length(resource_id) <= 256),

    -- Classification
    risk_tier       TEXT        NOT NULL
                    CHECK (risk_tier IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    outcome         TEXT        NOT NULL
                    CHECK (outcome IN ('SUCCESS','FAILURE','DENIED','PARTIAL','UNKNOWN')),

    -- Tamper-evidence chain
    prev_hash       TEXT        NOT NULL DEFAULT 'GENESIS',
    event_hmac      CHAR(64)    NOT NULL
                    CHECK (event_hmac ~ '^[0-9a-f]{64}$'),

    -- Optional context payload
    detail          JSONB,

    -- Index metadata: when this row was inserted into the hot-tier index
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Row-Level Security (HC-4) ─────────────────────────────────────────────────
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events;
CREATE POLICY audit_events_tenant_isolation ON audit_events
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Primary query pattern: auditor query by actor + date + tenant
CREATE INDEX IF NOT EXISTS idx_audit_events_actor_occurred
    ON audit_events (tenant_id, actor_id, occurred_at DESC);

-- Lookup by action for risk analysis
CREATE INDEX IF NOT EXISTS idx_audit_events_action
    ON audit_events (tenant_id, action, occurred_at DESC);

-- Lookup by resource
CREATE INDEX IF NOT EXISTS idx_audit_events_resource
    ON audit_events (tenant_id, resource_type, resource_id, occurred_at DESC);

-- Risk-tier + outcome for compliance queries
CREATE INDEX IF NOT EXISTS idx_audit_events_risk_outcome
    ON audit_events (tenant_id, risk_tier, outcome, occurred_at DESC);

-- Chain integrity lookup: look up predecessor by event_hmac
CREATE INDEX IF NOT EXISTS idx_audit_events_event_hmac
    ON audit_events (event_hmac);

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE  audit_events                IS 'Hot-tier index for WORM audit events (IMP-09). Authoritative record is in S3 append-only object storage.';
COMMENT ON COLUMN audit_events.actor_id       IS 'HC-6: HMAC-SHA256 hex digest of actor NID or email. Never a raw identifier.';
COMMENT ON COLUMN audit_events.tenant_id      IS 'HC-4: Owning tenant UUID. NOT NULL. Protected by RLS policy audit_events_tenant_isolation.';
COMMENT ON COLUMN audit_events.event_hmac     IS 'HMAC-SHA256 of the canonical event payload. Used for tamper detection.';
COMMENT ON COLUMN audit_events.prev_hash      IS 'event_hmac of the preceding event in this tenant partition (GENESIS for first event).';
COMMENT ON COLUMN audit_events.risk_tier      IS 'LOW | MEDIUM | HIGH | CRITICAL — classification of the audited operation.';
COMMENT ON COLUMN audit_events.outcome        IS 'SUCCESS | FAILURE | DENIED | PARTIAL | UNKNOWN — result of the audited operation.';
