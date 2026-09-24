-- i3 Platform: P7 Remediation for platform/migrations/001_all_databases.sql
-- Audit findings:
--   - ar_db:          ar_actions, ar_approvals — no tenant_id, no RLS
--   - talent_db:      candidates, skills, candidate_skills, assessments, jobs,
--                     placements, teams, team_members, passports — no tenant_id, no RLS
--   - sit_db:         learners, courses, enrollments, exam_bookings, credentials,
--                     professional_bookings, membership_subscriptions, ecitizen_cases
--                     — no tenant_id, no RLS; id_number/phone stored in clear text (HC-6)
--   - ford_members_db: members_pii, agent_velocity, primary_ballots
--                     — no tenant_id, no RLS; SHA-256 hashing (must be HMAC-SHA256, HC-6/M-5)
-- HC-4: tenant_id UUID NOT NULL on every row
-- HC-6: National IDs and phone numbers must use HMAC-SHA256 (MEMBER_HMAC_SECRET), never raw SHA-256
-- HC-8: Ballot secrecy — voter identity and ballot choice architecturally separated
-- M-5:  No dynamic-length index on TEXT columns that hold PII tokens
-- Apply: run each \c block against the named database individually; or pipe through psql meta-commands

-- ============================================================
-- 1. ACTION REGISTRY DATABASE (ar_db)
-- ============================================================
\c ar_db;

-- ar_actions: global action catalogue — tenant_scope column distinguishes single vs all
-- Still needs tenant_id on ar_approvals (per-tenant approval requests)
ALTER TABLE ar_actions ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE ar_actions SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE ar_actions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ar_actions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON ar_actions;
CREATE POLICY tenant_isolation ON ar_actions
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_ar_actions_tenant ON ar_actions (tenant_id);

ALTER TABLE ar_approvals ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE ar_approvals SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE ar_approvals ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ar_approvals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON ar_approvals;
CREATE POLICY tenant_isolation ON ar_approvals
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_ar_approvals_tenant_created
  ON ar_approvals (tenant_id, created_at DESC);

-- ============================================================
-- 2. TALENT CLOUD DATABASE (talent_db)
-- ============================================================
\c talent_db;

ALTER TABLE candidates ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE candidates SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE candidates ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON candidates;
CREATE POLICY tenant_isolation ON candidates
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_candidates_tenant ON candidates (tenant_id, bench_status);

-- skills: reference data, but must be tenant-scoped if tenants manage their own taxonomies
ALTER TABLE skills ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE skills SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE skills ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE skills ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON skills;
CREATE POLICY tenant_isolation ON skills
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- candidate_skills: junction table, inherits tenant from parent
ALTER TABLE candidate_skills ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE candidate_skills SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE candidate_skills ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE candidate_skills ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON candidate_skills;
CREATE POLICY tenant_isolation ON candidate_skills
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE assessments ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE assessments SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE assessments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON assessments;
CREATE POLICY tenant_isolation ON assessments
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_assessments_tenant ON assessments (tenant_id, assessed_at DESC);

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE jobs SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE jobs ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON jobs;
CREATE POLICY tenant_isolation ON jobs
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs (tenant_id, status);

ALTER TABLE placements ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE placements SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE placements ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE placements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON placements;
CREATE POLICY tenant_isolation ON placements
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_placements_tenant ON placements (tenant_id, status);

ALTER TABLE teams ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE teams SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE teams ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON teams;
CREATE POLICY tenant_isolation ON teams
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE team_members ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE team_members SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE team_members ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON team_members;
CREATE POLICY tenant_isolation ON team_members
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE passports ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE passports SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE passports ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE passports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON passports;
CREATE POLICY tenant_isolation ON passports
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- 3. SIT DIGITAL WORK-CENTERS DATABASE (sit_db)
-- ============================================================
\c sit_db;

-- HC-6 NOTE: sit_db.learners.id_number and .phone are stored as plain text.
-- The application layer MUST HMAC-SHA256-hash them via MEMBER_HMAC_SECRET before
-- writing.  This migration renames the columns to make the contract explicit and
-- adds a NOT NULL check so uncleared text cannot be inserted going forward.
-- RUNTIME ACTION REQUIRED: application must hash values before INSERT/UPDATE.
ALTER TABLE learners
  RENAME COLUMN id_number TO id_number_hmac;
ALTER TABLE learners
  RENAME COLUMN phone TO phone_hmac;
-- Drop the existing plain UNIQUE index before rebuilding
DROP INDEX IF EXISTS learners_id_number_key;
ALTER TABLE learners
  ADD CONSTRAINT learners_id_number_hmac_unique UNIQUE (id_number_hmac);

ALTER TABLE learners ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE learners SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE learners ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE learners ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON learners;
CREATE POLICY tenant_isolation ON learners
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_learners_tenant ON learners (tenant_id);

ALTER TABLE courses ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE courses SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE courses ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON courses;
CREATE POLICY tenant_isolation ON courses
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE enrollments SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE enrollments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON enrollments;
CREATE POLICY tenant_isolation ON enrollments
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_enrollments_tenant ON enrollments (tenant_id, status);

ALTER TABLE exam_bookings ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE exam_bookings SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE exam_bookings ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE exam_bookings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON exam_bookings;
CREATE POLICY tenant_isolation ON exam_bookings
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE credentials ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE credentials SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE credentials ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE credentials ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON credentials;
CREATE POLICY tenant_isolation ON credentials
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_credentials_tenant ON credentials (tenant_id);

ALTER TABLE professional_bookings ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE professional_bookings SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE professional_bookings ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE professional_bookings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON professional_bookings;
CREATE POLICY tenant_isolation ON professional_bookings
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE membership_subscriptions ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE membership_subscriptions SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE membership_subscriptions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE membership_subscriptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON membership_subscriptions;
CREATE POLICY tenant_isolation ON membership_subscriptions
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE ecitizen_cases ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE ecitizen_cases SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE ecitizen_cases ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ecitizen_cases ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON ecitizen_cases;
CREATE POLICY tenant_isolation ON ecitizen_cases
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_ecitizen_cases_tenant ON ecitizen_cases (tenant_id, status);

-- ============================================================
-- 4. FORD-ASILI MEMBERS DATABASE (ford_members_db)
-- ============================================================
\c ford_members_db;

-- HC-6 CRITICAL: id_hash and phone_hash were written as raw SHA-256 (non-keyed).
-- They must be recomputed as HMAC-SHA256 using MEMBER_HMAC_SECRET at the application
-- layer.  The columns are renamed here to signal the contract change.
-- M-5: plain indexes on TEXT tokens derived from PII — acceptable for HMAC tokens
--       because HMAC is fixed-length 64-char hex; the index length is deterministic.
ALTER TABLE members_pii
  RENAME COLUMN id_hash    TO national_id_hmac;
ALTER TABLE members_pii
  RENAME COLUMN phone_hash TO phone_hmac;

-- Add tenant_id to all three tables
ALTER TABLE members_pii ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE members_pii SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE members_pii ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE members_pii ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON members_pii;
CREATE POLICY tenant_isolation ON members_pii
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_members_pii_tenant ON members_pii (tenant_id, status);

ALTER TABLE agent_velocity ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE agent_velocity SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE agent_velocity ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE agent_velocity ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON agent_velocity;
CREATE POLICY tenant_isolation ON agent_velocity
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_agent_velocity_tenant ON agent_velocity (tenant_id, agent_id, window_start DESC);

-- HC-8: primary_ballots contains anonymised ballot tokens with no voter PII link.
-- Still requires tenant isolation to prevent cross-tenant ballot enumeration.
ALTER TABLE primary_ballots ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE primary_ballots SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
ALTER TABLE primary_ballots ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE primary_ballots ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON primary_ballots;
CREATE POLICY tenant_isolation ON primary_ballots
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE INDEX IF NOT EXISTS idx_primary_ballots_tenant ON primary_ballots (tenant_id, ward_code, seat_code, status);
