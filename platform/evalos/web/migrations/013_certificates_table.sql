-- ============================================================
-- Migration: 013_certificates_table.sql
-- Patches existing tables to align with the application schema.
-- All statements use IF NOT EXISTS / IF EXISTS so this is
-- fully idempotent and safe to re-run.
--
-- Changes:
--   certificates    → add tenant_id column + RLS policy
--   skills_passports → already correct; ensure RLS enabled
--   enrolment_queue  → add tenant_id column + RLS policy
-- ============================================================

BEGIN;

-- ── 1. certificates: add tenant_id (HC-4) ─────────────────────────────────
ALTER TABLE certificates
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_certificates_tenant  ON certificates (tenant_id);
CREATE INDEX IF NOT EXISTS idx_certificates_student ON certificates (student_id);
CREATE INDEX IF NOT EXISTS idx_certificates_attempt ON certificates (attempt_id);

ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS certificates_tenant_isolation ON certificates;
CREATE POLICY certificates_tenant_isolation ON certificates
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 2. enrolment_queue: add tenant_id (HC-4) ──────────────────────────────
ALTER TABLE enrolment_queue
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_enrolment_queue_tenant ON enrolment_queue (tenant_id);

ALTER TABLE enrolment_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS enrolment_queue_tenant_isolation ON enrolment_queue;
CREATE POLICY enrolment_queue_tenant_isolation ON enrolment_queue
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 3. skills_passports: RLS already enabled; ensure policy exists ─────────
DROP POLICY IF EXISTS skills_passports_tenant_isolation ON skills_passports;
CREATE POLICY skills_passports_tenant_isolation ON skills_passports
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

COMMIT;
