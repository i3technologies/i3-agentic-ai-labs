-- ============================================================
-- Migration: V1__baseline_tenant_rls.sql
-- Platform:  i3 AI Platform
-- Constraint: HC-4 — tenant_id UUID NOT NULL on every table
-- 
-- Run with Flyway: flyway -url=jdbc:postgresql://... migrate
-- Run manually:   psql $DATABASE_URL -f V1__baseline_tenant_rls.sql
--
-- Applies RLS (Row-Level Security) to all tenant-scoped tables
-- so that every query automatically filters to the caller's tenant.
--
-- Pattern:
--   1. Enable RLS on the table
--   2. Create a USING policy that checks app.tenant_id session var
--   3. Application code sets: SET LOCAL app.tenant_id = '<uuid>'
--      before every query (via asyncpg or pg Pool transaction wrapper)
-- ============================================================

-- ── Engage DB tables ─────────────────────────────────────────────────────────

-- campaigns
ALTER TABLE IF EXISTS campaigns ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS campaigns_tenant_isolation ON campaigns;
CREATE POLICY campaigns_tenant_isolation ON campaigns
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- contacts
ALTER TABLE IF EXISTS contacts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS contacts_tenant_isolation ON contacts;
CREATE POLICY contacts_tenant_isolation ON contacts
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- send_jobs
ALTER TABLE IF EXISTS send_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS send_jobs_tenant_isolation ON send_jobs;
CREATE POLICY send_jobs_tenant_isolation ON send_jobs
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- email_events
ALTER TABLE IF EXISTS email_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS email_events_tenant_isolation ON email_events;
CREATE POLICY email_events_tenant_isolation ON email_events
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- sms_events
ALTER TABLE IF EXISTS sms_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sms_events_tenant_isolation ON sms_events;
CREATE POLICY sms_events_tenant_isolation ON sms_events
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- inbound_messages
ALTER TABLE IF EXISTS inbound_messages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inbound_messages_tenant_isolation ON inbound_messages;
CREATE POLICY inbound_messages_tenant_isolation ON inbound_messages
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- webhook_events
ALTER TABLE IF EXISTS webhook_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS webhook_events_tenant_isolation ON webhook_events;
CREATE POLICY webhook_events_tenant_isolation ON webhook_events
  USING (tenant_id = current_setting('app.tenant_id')::uuid);


-- ── EvalOS DB tables ──────────────────────────────────────────────────────────

-- exams
ALTER TABLE IF EXISTS exams ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS exams_tenant_isolation ON exams;
CREATE POLICY exams_tenant_isolation ON exams
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- questions
ALTER TABLE IF EXISTS questions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS questions_tenant_isolation ON questions;
CREATE POLICY questions_tenant_isolation ON questions
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- quiz_attempts
ALTER TABLE IF EXISTS quiz_attempts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quiz_attempts_tenant_isolation ON quiz_attempts;
CREATE POLICY quiz_attempts_tenant_isolation ON quiz_attempts
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- enrolment_queue
ALTER TABLE IF EXISTS enrolment_queue ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS enrolment_queue_tenant_isolation ON enrolment_queue;
CREATE POLICY enrolment_queue_tenant_isolation ON enrolment_queue
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- certificates
ALTER TABLE IF EXISTS certificates ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS certificates_tenant_isolation ON certificates;
CREATE POLICY certificates_tenant_isolation ON certificates
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- ai_interviews
ALTER TABLE IF EXISTS ai_interviews ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_interviews_tenant_isolation ON ai_interviews;
CREATE POLICY ai_interviews_tenant_isolation ON ai_interviews
  USING (tenant_id = current_setting('app.tenant_id')::uuid);


-- ── PMaaS DB tables ───────────────────────────────────────────────────────────

-- campaigns (pmaas)
-- NOTE: pmaas uses a separate DB; apply this migration to that DB too
ALTER TABLE IF EXISTS pmaas_campaigns ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS pmaas_campaigns_tenant_isolation ON pmaas_campaigns;
CREATE POLICY pmaas_campaigns_tenant_isolation ON pmaas_campaigns
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- ward_data
ALTER TABLE IF EXISTS ward_data ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ward_data_tenant_isolation ON ward_data;
CREATE POLICY ward_data_tenant_isolation ON ward_data
  USING (tenant_id = current_setting('app.tenant_id')::uuid);


-- ── Agent Registry tables ─────────────────────────────────────────────────────

-- agent_decisions
ALTER TABLE IF EXISTS agent_decisions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agent_decisions_tenant_isolation ON agent_decisions;
CREATE POLICY agent_decisions_tenant_isolation ON agent_decisions
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- ar_approvals
ALTER TABLE IF EXISTS ar_approvals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ar_approvals_tenant_isolation ON ar_approvals;
CREATE POLICY ar_approvals_tenant_isolation ON ar_approvals
  USING (tenant_id = current_setting('app.tenant_id')::uuid);


-- ── Sensor check query (run after applying) ───────────────────────────────────
-- SC-C2: Verify all tenant-scoped tables have RLS enabled
--   SELECT tablename, rowsecurity
--   FROM pg_tables
--   WHERE schemaname = 'public'
--     AND tablename IN (
--       'campaigns','contacts','send_jobs','email_events','sms_events',
--       'inbound_messages','webhook_events','exams','questions',
--       'quiz_attempts','enrolment_queue','certificates','ai_interviews',
--       'pmaas_campaigns','ward_data','agent_decisions','ar_approvals'
--     )
--   ORDER BY tablename;
-- Expected: rowsecurity = true for every listed table.
