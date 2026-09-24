-- PMaaS: P7 Remediation — tenant_id + RLS for tables missed by 002
-- Audit finding: 002_add_tenant_id.sql omitted wards, volunteers,
--               campaign_activity, ai_briefings, voter_interactions
-- HC-4: tenant_id UUID NOT NULL on every table
-- P7:   Row-Level Security tenant isolation on all application tables
-- Apply: psql $PMAAS_DB_URL < migrations/003_rls_missing_tables.sql

BEGIN;

-- ── wards ─────────────────────────────────────────────────────────────────────
-- Ward reference data is shared per-tenant campaign scope; must be isolated.
ALTER TABLE wards ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE wards SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE wards ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE wards ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON wards;
CREATE POLICY tenant_isolation ON wards
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_wards_tenant_county
  ON wards (tenant_id, county);

-- ── volunteers ────────────────────────────────────────────────────────────────
ALTER TABLE volunteers ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE volunteers SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE volunteers ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE volunteers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON volunteers;
CREATE POLICY tenant_isolation ON volunteers
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_volunteers_tenant_created
  ON volunteers (tenant_id, created_at DESC);

-- ── campaign_activity ─────────────────────────────────────────────────────────
ALTER TABLE campaign_activity ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE campaign_activity SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE campaign_activity ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE campaign_activity ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON campaign_activity;
CREATE POLICY tenant_isolation ON campaign_activity
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_campaign_activity_tenant_created
  ON campaign_activity (tenant_id, created_at DESC);

-- ── ai_briefings ──────────────────────────────────────────────────────────────
ALTER TABLE ai_briefings ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE ai_briefings SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE ai_briefings ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ai_briefings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON ai_briefings;
CREATE POLICY tenant_isolation ON ai_briefings
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_ai_briefings_tenant_created
  ON ai_briefings (tenant_id, created_at DESC);

-- ── voter_interactions ────────────────────────────────────────────────────────
-- HC-8: Voter identity and ballot choice are architecturally separated via
--        Fabric private data collections; this table holds interaction metadata only.
ALTER TABLE voter_interactions ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE voter_interactions SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE voter_interactions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE voter_interactions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON voter_interactions;
CREATE POLICY tenant_isolation ON voter_interactions
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_voter_interactions_tenant_created
  ON voter_interactions (tenant_id, created_at DESC);

-- ── Idempotency guard: safe re-apply for tables already handled by 002 ────────
DROP POLICY IF EXISTS tenant_isolation ON campaigns;
CREATE POLICY tenant_isolation ON campaigns
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

DROP POLICY IF EXISTS tenant_isolation ON voters;
CREATE POLICY tenant_isolation ON voters
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

DROP POLICY IF EXISTS tenant_isolation ON ward_targets;
CREATE POLICY tenant_isolation ON ward_targets
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

COMMIT;
