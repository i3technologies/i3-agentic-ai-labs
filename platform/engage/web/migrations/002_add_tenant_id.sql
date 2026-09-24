-- i3-Engage: Add tenant_id + Row-Level Security
-- Apply: psql $ENGAGE_DB_URL < migrations/002_add_tenant_id.sql
-- Step Reference: STEP-P2-05 (i3-platform-atomic-execution-plan.md)
-- HC-4: tenant_id UUID NOT NULL on every table
-- HC-6: HMAC-SHA256 for identifiers; plain UUIDs safe here (not PII)

BEGIN;

-- ── inbound_messages: create if not yet present (webhook inbound log) ─────
CREATE TABLE IF NOT EXISTS inbound_messages (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_email TEXT NOT NULL,
  subject    TEXT,
  body_text  TEXT,
  body_html  TEXT,
  raw_headers JSONB DEFAULT '{}',
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Step 1: Add nullable tenant_id column to all four tables ──────────────
ALTER TABLE email_campaigns   ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE contacts          ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE contact_lists     ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE inbound_messages  ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- ── Step 2: Backfill — assign every existing row to i3 production tenant ──
-- Default tenant: 00000000-0000-0000-0000-000000000001
UPDATE email_campaigns  SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE contacts         SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE contact_lists    SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
UPDATE inbound_messages SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;

-- ── Step 3: Enforce NOT NULL after backfill ────────────────────────────────
ALTER TABLE email_campaigns  ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE contacts         ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE contact_lists    ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE inbound_messages ALTER COLUMN tenant_id SET NOT NULL;

-- ── Step 4: Enable Row-Level Security ─────────────────────────────────────
ALTER TABLE email_campaigns  ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE contact_lists    ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbound_messages ENABLE ROW LEVEL SECURITY;

-- ── Step 5: Tenant isolation policies ─────────────────────────────────────
-- Callers must SET app.tenant_id = '<uuid>' before querying.
-- Superuser / service role (BYPASSRLS) is exempt — used by migration runner only.
CREATE POLICY tenant_isolation ON email_campaigns
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

CREATE POLICY tenant_isolation ON contacts
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

CREATE POLICY tenant_isolation ON contact_lists
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

CREATE POLICY tenant_isolation ON inbound_messages
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- ── Step 6: Composite indexes for tenant-scoped queries ───────────────────
CREATE INDEX IF NOT EXISTS idx_email_campaigns_tenant_created
  ON email_campaigns  (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contacts_tenant_created
  ON contacts         (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contact_lists_tenant_created
  ON contact_lists    (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_inbound_messages_tenant_received
  ON inbound_messages (tenant_id, received_at DESC);

COMMIT;
