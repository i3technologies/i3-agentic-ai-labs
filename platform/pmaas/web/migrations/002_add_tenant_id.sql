-- PMaaS: Add tenant_id + Row-Level Security
-- Apply: psql $PMAAS_DB_URL < migrations/002_add_tenant_id.sql
-- Step Reference: STEP-P2-05 (i3-platform-atomic-execution-plan.md)
-- HC-4: tenant_id UUID NOT NULL on every table
-- HC-8: Voter identity and ballot choice architecturally separated (private data collections — Fabric layer)

BEGIN;

-- ── Step 1: Add nullable tenant_id column ─────────────────────────────────
ALTER TABLE campaigns    ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE voters       ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE ward_targets ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- ── Step 2: Backfill — assign every existing row to i3 production tenant ──
-- Default tenant: 00000000-0000-0000-0000-000000000001
UPDATE campaigns    SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE voters       SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE ward_targets SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;

-- ── Step 3: Enforce NOT NULL after backfill ────────────────────────────────
ALTER TABLE campaigns    ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE voters       ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ward_targets ALTER COLUMN tenant_id SET NOT NULL;

-- ── Step 4: Enable Row-Level Security ─────────────────────────────────────
ALTER TABLE campaigns    ENABLE ROW LEVEL SECURITY;
ALTER TABLE voters       ENABLE ROW LEVEL SECURITY;
ALTER TABLE ward_targets ENABLE ROW LEVEL SECURITY;

-- ── Step 5: Tenant isolation policies ─────────────────────────────────────
-- Callers must SET app.tenant_id = '<uuid>' before querying.
-- Superuser / service role (BYPASSRLS) is exempt — used by migration runner only.
CREATE POLICY tenant_isolation ON campaigns
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

CREATE POLICY tenant_isolation ON voters
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

CREATE POLICY tenant_isolation ON ward_targets
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- ── Step 6: Composite indexes for tenant-scoped queries ───────────────────
CREATE INDEX IF NOT EXISTS idx_campaigns_tenant_created
  ON campaigns    (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_voters_tenant_created
  ON voters       (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ward_targets_tenant_created
  ON ward_targets (tenant_id, created_at DESC);

COMMIT;
