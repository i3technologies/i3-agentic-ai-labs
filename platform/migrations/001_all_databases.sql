-- i3 Platform Database Initialisation Script
-- Creates: ar_db, talent_db, sit_db, ford_members_db
-- Run as: i3admin (SUPERUSER) via psql against PGBouncer on i3-postgres-pgbouncer.i3-data.svc:5432

-- ============================================================
-- 1. ACTION REGISTRY DATABASE (i3-AR)
-- ============================================================
CREATE DATABASE ar_db;
\c ar_db;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE ar_actions (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT        NOT NULL UNIQUE,
  vertical         TEXT        NOT NULL,  -- ar | sit | talent | ford | global
  risk_tier        INT         NOT NULL CHECK (risk_tier BETWEEN 0 AND 4),
  description      TEXT,
  mcp_tool         TEXT,
  approval_required BOOLEAN    DEFAULT false,
  enabled          BOOLEAN     DEFAULT true,
  created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ar_approvals (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  action_name  TEXT        REFERENCES ar_actions(name),
  requested_by TEXT        NOT NULL,
  payload      JSONB,
  status       TEXT        DEFAULT 'pending',
  reviewed_by  TEXT,
  reviewed_at  TIMESTAMPTZ,
  trace_id     TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON ar_approvals(status, created_at);
CREATE INDEX ON ar_approvals(requested_by, created_at);

-- Seed Tier 0-4 actions
INSERT INTO ar_actions (name, vertical, risk_tier, description, mcp_tool, approval_required) VALUES
  ('read_db_schema',         'global', 0, 'Read table/column metadata from PostgreSQL',     'read_db_schema',         false),
  ('query_vector_context',   'global', 0, 'Semantic search across ChromaDB collections',    'query_curriculum_vector',false),
  ('inspect_pod_logs',       'global', 0, 'Read pod logs from cluster',                     NULL,                     false),
  ('ask_model',              'global', 0, 'Call LiteLLM model - no side effects',            NULL,                     false),
  ('draft_email_campaign',   'global', 1, 'Draft outreach email via LiteLLM',               NULL,                     false),
  ('generate_code_plan',     'global', 1, 'Generate structured execution plan',             NULL,                     false),
  ('draft_sql_migration',    'global', 1, 'Draft SQL migration file for review',            NULL,                     false),
  ('execute_python_sandbox', 'global', 2, 'Run Python code in ephemeral OCP Job',           'execute_sandboxed_code', false),
  ('run_unit_tests',         'global', 2, 'Run test suite in sandbox',                      'execute_sandboxed_code', false),
  ('run_db_query_readonly',  'global', 2, 'Execute read-only SELECT via sandbox',           'execute_sandboxed_code', false),
  ('apply_db_migration',     'global', 3, 'Apply SQL migration to PostgreSQL',              'execute_sandboxed_code', true),
  ('write_memory_file',      'global', 3, 'Write to _context/ memory store',               NULL,                     true),
  ('create_keycloak_user',   'global', 3, 'Create user/role in Keycloak realm',             NULL,                     true),
  ('trigger_tekton_pipeline','global', 4, 'Trigger Tekton CI/CD pipeline',                 NULL,                     true),
  ('oc_apply_manifest',      'global', 4, 'Apply Kubernetes manifest to cluster',           NULL,                     true),
  ('promote_to_production',  'global', 4, 'Promote image tag to production deployment',     NULL,                     true);


-- ============================================================
-- 2. TALENT CLOUD DATABASE
-- ============================================================
CREATE DATABASE talent_db;
\c talent_db;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE candidates (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  keycloak_sub    TEXT        UNIQUE NOT NULL,
  full_name       TEXT        NOT NULL,
  email           TEXT,
  phone           TEXT,
  location        TEXT,
  source          TEXT        DEFAULT 'direct',   -- direct | sit | evalos
  bench_status    TEXT        DEFAULT 'available',-- available | placed | inactive
  evalos_passport_id TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE skills (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT UNIQUE NOT NULL,
  category    TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE candidate_skills (
  candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
  skill_id     UUID REFERENCES skills(id) ON DELETE CASCADE,
  proficiency  INT  CHECK (proficiency BETWEEN 1 AND 5),
  endorsed_by  TEXT,
  PRIMARY KEY (candidate_id, skill_id)
);

CREATE TABLE assessments (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id    UUID        REFERENCES candidates(id),
  evalos_session  TEXT,
  score           DECIMAL(5,2),
  passed          BOOLEAN,
  trace_id        TEXT,
  assessed_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE jobs (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  title        TEXT        NOT NULL,
  client       TEXT,
  description  TEXT,
  skills_req   JSONB,
  status       TEXT        DEFAULT 'open',
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE placements (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID        REFERENCES candidates(id),
  job_id        UUID        REFERENCES jobs(id),
  match_score   DECIMAL(5,2),
  trace_id      TEXT,
  status        TEXT        DEFAULT 'proposed',
  approved_by   TEXT,
  placed_at     TIMESTAMPTZ
);

CREATE TABLE teams (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  client      TEXT,
  description TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE team_members (
  team_id      UUID REFERENCES teams(id) ON DELETE CASCADE,
  candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
  role         TEXT,
  joined_at    TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (team_id, candidate_id)
);

CREATE TABLE passports (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID        REFERENCES candidates(id) UNIQUE,
  badges        JSONB       DEFAULT '[]',
  cert_hashes   JSONB       DEFAULT '[]',
  last_updated  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON candidates(bench_status);
CREATE INDEX ON assessments(candidate_id, assessed_at);
CREATE INDEX ON placements(candidate_id, status);


-- ============================================================
-- 3. SIT DIGITAL WORK-CENTERS DATABASE
-- ============================================================
CREATE DATABASE sit_db;
\c sit_db;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE learners (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  keycloak_sub TEXT        UNIQUE NOT NULL,
  full_name    TEXT        NOT NULL,
  id_number    TEXT        UNIQUE,
  phone        TEXT,
  email        TEXT,
  ward         TEXT,
  consent_at   TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE courses (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code            TEXT UNIQUE NOT NULL,
  title           TEXT NOT NULL,
  tvet_level      TEXT,
  duration_weeks  INT,
  delivery        TEXT DEFAULT 'blended'
);

CREATE TABLE enrollments (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id  UUID        REFERENCES learners(id),
  course_id   UUID        REFERENCES courses(id),
  enrolled_at TIMESTAMPTZ DEFAULT now(),
  status      TEXT        DEFAULT 'active'
);

CREATE TABLE exam_bookings (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id     UUID        REFERENCES enrollments(id),
  evalos_session_id TEXT,
  booked_at         TIMESTAMPTZ DEFAULT now(),
  status            TEXT        DEFAULT 'scheduled'
);

CREATE TABLE credentials (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id      UUID        REFERENCES learners(id),
  course_id       UUID        REFERENCES courses(id),
  issued_at       TIMESTAMPTZ DEFAULT now(),
  cert_hash       TEXT        NOT NULL,
  qr_token        TEXT        UNIQUE,
  talent_node_id  TEXT
);

CREATE TABLE professional_bookings (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id        UUID        REFERENCES learners(id),
  professional_id  TEXT        NOT NULL,
  service_type     TEXT,
  scheduled_at     TIMESTAMPTZ,
  commission_pct   DECIMAL(5,2) DEFAULT 20.0,
  status           TEXT        DEFAULT 'pending',
  webrtc_room_id   TEXT
);

CREATE TABLE membership_subscriptions (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id  UUID        REFERENCES learners(id),
  tier        TEXT        NOT NULL,
  starts_at   TIMESTAMPTZ,
  expires_at  TIMESTAMPTZ,
  qr_token    TEXT        UNIQUE,
  active      BOOLEAN     DEFAULT true
);

CREATE TABLE ecitizen_cases (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  citizen_id   UUID        REFERENCES learners(id),
  service      TEXT        NOT NULL,
  status       TEXT        DEFAULT 'open',
  n8n_exec_id  TEXT,
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON enrollments(learner_id);
CREATE INDEX ON exam_bookings(enrollment_id);
CREATE INDEX ON credentials(learner_id);
CREATE INDEX ON credentials(qr_token);
CREATE INDEX ON ecitizen_cases(citizen_id, status);
CREATE INDEX ON membership_subscriptions(learner_id, active);


-- ============================================================
-- 4. FORD-ASILI MEMBERS DATABASE (OFF-CHAIN PII STORE)
-- ============================================================
CREATE DATABASE ford_members_db;
\c ford_members_db;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE members_pii (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  id_hash         TEXT        UNIQUE NOT NULL,   -- SHA-256(national_id) — mirrors on-chain key
  phone_hash      TEXT        NOT NULL,           -- SHA-256(phone) — dedup key
  ward_code       TEXT        NOT NULL,
  constituency    TEXT,
  county          TEXT,
  consent_at      TIMESTAMPTZ NOT NULL,
  otp_verified    BOOLEAN     DEFAULT false,
  status          TEXT        DEFAULT 'pending',  -- pending | verified | flagged | rejected
  flagged_reason  TEXT,
  agent_id        TEXT,
  fabric_tx_id    TEXT,                           -- Fabric transaction ID after ledger write
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Velocity monitoring for fraud detection
CREATE TABLE agent_velocity (
  agent_id         TEXT        NOT NULL,
  window_start     TIMESTAMPTZ NOT NULL,
  registrations    INT         DEFAULT 0,
  verified_count   INT         DEFAULT 0,
  flagged_count    INT         DEFAULT 0,
  PRIMARY KEY (agent_id, window_start)
);

CREATE TABLE primary_ballots (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  ballot_token    TEXT        UNIQUE NOT NULL,    -- anonymised — no link to voter PII here
  ward_code       TEXT        NOT NULL,
  seat_code       TEXT        NOT NULL,
  cast_at         TIMESTAMPTZ,
  status          TEXT        DEFAULT 'pending',   -- pending | cast | invalid
  fabric_tx_id    TEXT
);

CREATE INDEX ON members_pii(status, ward_code);
CREATE INDEX ON members_pii(agent_id, created_at);
CREATE INDEX ON members_pii(otp_verified, status);
CREATE INDEX ON primary_ballots(ward_code, seat_code, status);

-- Create dedicated DB users
\c ar_db;
CREATE USER ar_app WITH PASSWORD 'REPLACE_AR_PASSWORD';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ar_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ar_app;

\c talent_db;
CREATE USER talent_app WITH PASSWORD 'REPLACE_TALENT_PASSWORD';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO talent_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO talent_app;

\c sit_db;
CREATE USER sit_app WITH PASSWORD 'REPLACE_SIT_PASSWORD';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sit_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sit_app;

\c ford_members_db;
CREATE USER ford_app WITH PASSWORD 'REPLACE_FORD_PASSWORD';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ford_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ford_app;
