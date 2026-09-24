-- FORD Asili: Add tenant_id + Row-Level Security
-- Apply: psql $FORD_DB_URL < migrations/002_add_tenant_id.sql
-- Step Reference: STEP-P2-05 (i3-platform-atomic-execution-plan.md)
-- HC-4: tenant_id UUID NOT NULL on every table
-- HC-6: member identifiers use HMAC-SHA256 (handled at application layer, not stored raw here)
-- HC-8: Ballot secrecy enforced via Fabric private data collections (separate from this layer)

BEGIN;

-- ── members_pii: create if not yet present ────────────────────────────────
-- National IDs and phones are stored as HMAC-SHA256 tokens (never raw) per HC-6.
CREATE TABLE IF NOT EXISTS members_pii (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  national_id_hmac TEXT NOT NULL UNIQUE,
  phone_hmac       TEXT NOT NULL UNIQUE,
  agent_id         TEXT NOT NULL,
  flagged_reason   TEXT,           -- retained for backward-compat; no longer written (STEP-P1-05)
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_members_pii_national_id ON members_pii (national_id_hmac);

-- ── agent_velocity: create if not yet present ─────────────────────────────
-- Per-agent registration rate tracking (see STEP-P1-05 for OTP rate-limit via Redis).
CREATE TABLE IF NOT EXISTS agent_velocity (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id     TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  reg_count    INTEGER NOT NULL DEFAULT 0,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_velocity_agent_window ON agent_velocity (agent_id, window_start DESC);

-- ── Step 1: Add nullable tenant_id column ─────────────────────────────────
ALTER TABLE members_pii    ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE agent_velocity ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- ── Step 2: Backfill — assign every existing row to i3 production tenant ──
-- Default tenant: 00000000-0000-0000-0000-000000000001
UPDATE members_pii    SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE agent_velocity SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;

-- ── Step 3: Enforce NOT NULL after backfill ────────────────────────────────
ALTER TABLE members_pii    ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE agent_velocity ALTER COLUMN tenant_id SET NOT NULL;

-- ── Step 4: Enable Row-Level Security ─────────────────────────────────────
-- Critical: PII table must be RLS-isolated across tenants (HC-4, HC-6).
ALTER TABLE members_pii    ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_velocity ENABLE ROW LEVEL SECURITY;

-- ── Step 5: Tenant isolation policies ─────────────────────────────────────
-- Callers must SET app.tenant_id = '<uuid>' before querying.
-- Superuser / service role (BYPASSRLS) is exempt — used by migration runner only.
CREATE POLICY tenant_isolation ON members_pii
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

CREATE POLICY tenant_isolation ON agent_velocity
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- ── Step 6: Composite indexes for tenant-scoped queries ───────────────────
CREATE INDEX IF NOT EXISTS idx_members_pii_tenant_created
  ON members_pii    (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_velocity_tenant_window
  ON agent_velocity (tenant_id, window_start DESC);

COMMIT;
