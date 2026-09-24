-- ============================================================
-- apply_tenant_id_remediation.sql
-- Phase 1 Step 2 Remediation: Apply all pending tenant_id + RLS migrations
-- to engage_db, pmaas_db, ford_members_db, evalos_db
--
-- This script is IDEMPOTENT — safe to re-run.
-- Uses ADD COLUMN IF NOT EXISTS, DROP POLICY IF EXISTS, CREATE INDEX IF NOT EXISTS.
-- Run per-database: psql -d <db> -f apply_tenant_id_remediation.sql
-- DO NOT run against i3_platform or postgres; it is database-specific.
-- ============================================================

-- ── Helper: detect which DB we are connected to ──────────────────────────
-- (Each section is guarded by a DO block that checks current_database())

-- ============================================================
-- ENGAGE_DB section
-- ============================================================
DO $$ BEGIN IF current_database() = 'engage_db' THEN RAISE NOTICE 'Running engage_db remediation'; END IF; END $$;

DO $guard$
BEGIN
  IF current_database() != 'engage_db' THEN RETURN; END IF;

  -- contacts
  ALTER TABLE contacts ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE contacts SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE contacts ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON contacts;
  CREATE POLICY tenant_isolation ON contacts USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_contacts_tenant_created ON contacts (tenant_id, created_at DESC);

  -- contact_lists
  ALTER TABLE contact_lists ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE contact_lists SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE contact_lists ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE contact_lists ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON contact_lists;
  CREATE POLICY tenant_isolation ON contact_lists USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_contact_lists_tenant_created ON contact_lists (tenant_id, created_at DESC);

  -- inbound_messages
  ALTER TABLE inbound_messages ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE inbound_messages SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE inbound_messages ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE inbound_messages ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON inbound_messages;
  CREATE POLICY tenant_isolation ON inbound_messages USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_inbound_messages_tenant_received ON inbound_messages (tenant_id, received_at DESC);

  -- email_campaigns (re-assert policy in case it was partial)
  DROP POLICY IF EXISTS tenant_isolation ON email_campaigns;
  CREATE POLICY tenant_isolation ON email_campaigns USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_email_campaigns_tenant_created ON email_campaigns (tenant_id, created_at DESC);

  -- contact_events (migration 003)
  ALTER TABLE contact_events ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE contact_events SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE contact_events ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE contact_events ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON contact_events;
  CREATE POLICY tenant_isolation ON contact_events USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_contact_events_tenant_created ON contact_events (tenant_id, created_at DESC);

  -- email_sends
  ALTER TABLE email_sends ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE email_sends SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE email_sends ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE email_sends ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON email_sends;
  CREATE POLICY tenant_isolation ON email_sends USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_email_sends_tenant_sent ON email_sends (tenant_id, sent_at DESC NULLS LAST);

  -- sms_messages
  ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE sms_messages SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE sms_messages ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE sms_messages ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON sms_messages;
  CREATE POLICY tenant_isolation ON sms_messages USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_sms_messages_tenant_created ON sms_messages (tenant_id, created_at DESC);

  -- webhook_events (exists in engage_db per table list)
  ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE webhook_events SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE webhook_events ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON webhook_events;
  CREATE POLICY tenant_isolation ON webhook_events USING (tenant_id = current_setting('app.tenant_id')::UUID);

  RAISE NOTICE 'engage_db remediation complete';
END;
$guard$;

-- ============================================================
-- PMAAS_DB section
-- ============================================================
DO $guard$
BEGIN
  IF current_database() != 'pmaas_db' THEN RETURN; END IF;

  -- campaigns
  ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE campaigns SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE campaigns ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON campaigns;
  CREATE POLICY tenant_isolation ON campaigns USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_campaigns_tenant_created ON campaigns (tenant_id, created_at DESC);

  -- voters
  ALTER TABLE voters ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE voters SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE voters ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE voters ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON voters;
  CREATE POLICY tenant_isolation ON voters USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_voters_tenant_created ON voters (tenant_id, created_at DESC);

  -- ward_targets
  ALTER TABLE ward_targets ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE ward_targets SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE ward_targets ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE ward_targets ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON ward_targets;
  CREATE POLICY tenant_isolation ON ward_targets USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_ward_targets_tenant_created ON ward_targets (tenant_id, created_at DESC);

  -- wards
  ALTER TABLE wards ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE wards SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE wards ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE wards ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON wards;
  CREATE POLICY tenant_isolation ON wards USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_wards_tenant_county ON wards (tenant_id, county);

  -- volunteers
  ALTER TABLE volunteers ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE volunteers SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE volunteers ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE volunteers ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON volunteers;
  CREATE POLICY tenant_isolation ON volunteers USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_volunteers_tenant_created ON volunteers (tenant_id, created_at DESC);

  -- campaign_activity
  ALTER TABLE campaign_activity ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE campaign_activity SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE campaign_activity ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE campaign_activity ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON campaign_activity;
  CREATE POLICY tenant_isolation ON campaign_activity USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_campaign_activity_tenant_created ON campaign_activity (tenant_id, created_at DESC);

  -- ai_briefings
  ALTER TABLE ai_briefings ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE ai_briefings SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE ai_briefings ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE ai_briefings ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON ai_briefings;
  CREATE POLICY tenant_isolation ON ai_briefings USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_ai_briefings_tenant_created ON ai_briefings (tenant_id, created_at DESC);

  -- voter_interactions
  ALTER TABLE voter_interactions ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE voter_interactions SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE voter_interactions ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE voter_interactions ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON voter_interactions;
  CREATE POLICY tenant_isolation ON voter_interactions USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_voter_interactions_tenant_created ON voter_interactions (tenant_id, created_at DESC);

  RAISE NOTICE 'pmaas_db remediation complete';
END;
$guard$;

-- ============================================================
-- FORD_MEMBERS_DB section
-- ============================================================
DO $guard$
BEGIN
  IF current_database() != 'ford_members_db' THEN RETURN; END IF;

  -- members_pii
  ALTER TABLE members_pii ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE members_pii SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE members_pii ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE members_pii ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON members_pii;
  CREATE POLICY tenant_isolation ON members_pii USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_members_pii_tenant_created ON members_pii (tenant_id, created_at DESC);

  -- agent_velocity
  ALTER TABLE agent_velocity ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE agent_velocity SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE agent_velocity ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE agent_velocity ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON agent_velocity;
  CREATE POLICY tenant_isolation ON agent_velocity USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_agent_velocity_tenant_window ON agent_velocity (tenant_id, window_start DESC);

  -- primary_ballots (HC-8: anonymised tokens, still needs tenant isolation)
  ALTER TABLE primary_ballots ADD COLUMN IF NOT EXISTS tenant_id UUID;
  UPDATE primary_ballots SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
  ALTER TABLE primary_ballots ALTER COLUMN tenant_id SET NOT NULL;
  ALTER TABLE primary_ballots ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS tenant_isolation ON primary_ballots;
  CREATE POLICY tenant_isolation ON primary_ballots USING (tenant_id = current_setting('app.tenant_id')::UUID);
  CREATE INDEX IF NOT EXISTS idx_primary_ballots_tenant ON primary_ballots (tenant_id, ward_code, seat_code, status);

  RAISE NOTICE 'ford_members_db remediation complete';
END;
$guard$;

-- ============================================================
-- EVALOS_DB section — add tenant_id to tables missing it
-- (questions, exams, quiz_attempts already have it per live check)
-- ============================================================
DO $guard$
BEGIN
  IF current_database() != 'evalos_db' THEN RETURN; END IF;

  -- questions (already has tenant_id per live check — re-assert RLS only)
  DROP POLICY IF EXISTS questions_tenant_isolation ON questions;
  ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
  CREATE POLICY questions_tenant_isolation ON questions
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- exams
  DROP POLICY IF EXISTS exams_tenant_isolation ON exams;
  ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
  CREATE POLICY exams_tenant_isolation ON exams
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- quiz_attempts (attempt_answers is a child; add tenant_id)
  DROP POLICY IF EXISTS quiz_attempts_tenant_isolation ON quiz_attempts;
  ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY;
  CREATE POLICY quiz_attempts_tenant_isolation ON quiz_attempts
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- Tables confirmed WITHOUT tenant_id in live check — add them now
  -- questions already has it; exams already has it; quiz_attempts already has it
  -- The following DO NOT have tenant_id yet per the live state query:

  -- ai_interviews (no tenant_id in live state)
  ALTER TABLE ai_interviews ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';
  ALTER TABLE ai_interviews ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS ai_interviews_tenant_isolation ON ai_interviews;
  CREATE POLICY ai_interviews_tenant_isolation ON ai_interviews
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- question_sets
  ALTER TABLE question_sets ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';
  ALTER TABLE question_sets ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS question_sets_tenant_isolation ON question_sets;
  CREATE POLICY question_sets_tenant_isolation ON question_sets
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- topics (reference data but needs isolation)
  ALTER TABLE topics ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';
  ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS topics_tenant_isolation ON topics;
  CREATE POLICY topics_tenant_isolation ON topics
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- code_submissions
  ALTER TABLE code_submissions ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';
  ALTER TABLE code_submissions ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS code_submissions_tenant_isolation ON code_submissions;
  CREATE POLICY code_submissions_tenant_isolation ON code_submissions
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- exam_banks
  ALTER TABLE exam_banks ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';
  ALTER TABLE exam_banks ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS exam_banks_tenant_isolation ON exam_banks;
  CREATE POLICY exam_banks_tenant_isolation ON exam_banks
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  -- skills_passports (already has it per live check — re-assert RLS)
  DROP POLICY IF EXISTS skills_passports_tenant_isolation ON skills_passports;
  ALTER TABLE skills_passports ENABLE ROW LEVEL SECURITY;
  CREATE POLICY skills_passports_tenant_isolation ON skills_passports
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

  RAISE NOTICE 'evalos_db remediation complete';
END;
$guard$;
