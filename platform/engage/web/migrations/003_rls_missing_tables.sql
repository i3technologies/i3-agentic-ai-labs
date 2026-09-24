-- i3-Engage: P7 Remediation — tenant_id + RLS for tables missed by 002
-- Audit finding: 002_add_tenant_id.sql omitted contact_events, email_sends, sms_messages
-- HC-4: tenant_id UUID NOT NULL on every table
-- P7:   Row-Level Security tenant isolation on all application tables
-- Apply: psql $ENGAGE_DB_URL < migrations/003_rls_missing_tables.sql

BEGIN;

-- ── contact_events ────────────────────────────────────────────────────────────
ALTER TABLE contact_events ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE contact_events SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE contact_events ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE contact_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON contact_events;
CREATE POLICY tenant_isolation ON contact_events
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_contact_events_tenant_created
  ON contact_events (tenant_id, created_at DESC);

-- ── email_sends ───────────────────────────────────────────────────────────────
ALTER TABLE email_sends ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE email_sends SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE email_sends ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE email_sends ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON email_sends;
CREATE POLICY tenant_isolation ON email_sends
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_email_sends_tenant_sent
  ON email_sends (tenant_id, sent_at DESC NULLS LAST);

-- ── sms_messages ──────────────────────────────────────────────────────────────
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE sms_messages SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE sms_messages ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE sms_messages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sms_messages;
CREATE POLICY tenant_isolation ON sms_messages
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_sms_messages_tenant_created
  ON sms_messages (tenant_id, created_at DESC);

-- ── Idempotency guard: re-apply DROP/CREATE on tables already handled by 002 ─
-- (safe no-ops if 002 already ran; DROP IF EXISTS prevents duplicate-policy error)
DROP POLICY IF EXISTS tenant_isolation ON email_campaigns;
CREATE POLICY tenant_isolation ON email_campaigns
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

DROP POLICY IF EXISTS tenant_isolation ON contacts;
CREATE POLICY tenant_isolation ON contacts
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

DROP POLICY IF EXISTS tenant_isolation ON contact_lists;
CREATE POLICY tenant_isolation ON contact_lists
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

DROP POLICY IF EXISTS tenant_isolation ON inbound_messages;
CREATE POLICY tenant_isolation ON inbound_messages
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

COMMIT;
