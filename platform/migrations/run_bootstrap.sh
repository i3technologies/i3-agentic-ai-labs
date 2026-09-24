#!/bin/bash
# i3 Platform — DB bootstrap script
# Run inside i3-postgres-primary-hffm-0 -c database
#
# SCRUBBED (STEP-P1-01): hardcoded PGPASSWORD and DB user passwords removed.
# Retrieve at runtime via OpenBao before running this script:
#   export PGPASSWORD=$(vault kv get -field=password i3/postgres/admin)
#   export AR_PASS=$(vault kv get -field=password i3/ar/db)
#   export TALENT_PASS=$(vault kv get -field=password i3/talent/db)
#   export SIT_PASS=$(vault kv get -field=password i3/sit/db)
#   export FORD_PASS=$(vault kv get -field=password i3/ford/db)

if [ -z "$PGPASSWORD" ]; then
  PGPASSWORD=$(vault kv get -field=password i3/postgres/admin 2>/dev/null)
fi
if [ -z "$AR_PASS" ];     then AR_PASS=$(vault kv get -field=password i3/ar/db 2>/dev/null); fi
if [ -z "$TALENT_PASS" ]; then TALENT_PASS=$(vault kv get -field=password i3/talent/db 2>/dev/null); fi
if [ -z "$SIT_PASS" ];    then SIT_PASS=$(vault kv get -field=password i3/sit/db 2>/dev/null); fi
if [ -z "$FORD_PASS" ];   then FORD_PASS=$(vault kv get -field=password i3/ford/db 2>/dev/null); fi

for VAR in PGPASSWORD AR_PASS TALENT_PASS SIT_PASS FORD_PASS; do
  if [ -z "$(eval echo \$$VAR)" ]; then
    echo "ERROR: $VAR is not set and OpenBao lookup failed" >&2; exit 1
  fi
done

PGHOST='i3-postgres-primary.i3-data.svc'
PGPORT='5432'
PGUSER='i3admin'
export PGPASSWORD PGHOST PGPORT PGUSER

echo "==> Creating databases..."
psql -d i3_platform -c "CREATE DATABASE ar_db;" 2>&1 || echo "ar_db already exists"
psql -d i3_platform -c "CREATE DATABASE talent_db;" 2>&1 || echo "talent_db already exists"
psql -d i3_platform -c "CREATE DATABASE sit_db;" 2>&1 || echo "sit_db already exists"
psql -d i3_platform -c "CREATE DATABASE ford_members_db;" 2>&1 || echo "ford_members_db already exists"

echo "==> Bootstrapping ar_db..."
psql -d ar_db << 'EOSQL'
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS ar_actions (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT        NOT NULL UNIQUE,
  vertical         TEXT        NOT NULL,
  risk_tier        INT         NOT NULL CHECK (risk_tier BETWEEN 0 AND 4),
  description      TEXT,
  mcp_tool         TEXT,
  approval_required BOOLEAN    DEFAULT false,
  enabled          BOOLEAN     DEFAULT true,
  created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ar_approvals (
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

CREATE INDEX IF NOT EXISTS ar_approvals_status_idx ON ar_approvals(status, created_at);

INSERT INTO ar_actions (name, vertical, risk_tier, description, mcp_tool, approval_required) VALUES
  ('read_db_schema',         'global', 0, 'Read table/column metadata from PostgreSQL',   'read_db_schema',         false),
  ('query_vector_context',   'global', 0, 'Semantic search across ChromaDB',              'query_curriculum_vector',false),
  ('ask_model',              'global', 0, 'Call LiteLLM - no side effects',               NULL,                     false),
  ('draft_email_campaign',   'global', 1, 'Draft outreach email via LiteLLM',             NULL,                     false),
  ('generate_code_plan',     'global', 1, 'Generate structured execution plan',           NULL,                     false),
  ('draft_sql_migration',    'global', 1, 'Draft SQL migration file for review',          NULL,                     false),
  ('execute_python_sandbox', 'global', 2, 'Run Python in ephemeral OCP Job',              'execute_sandboxed_code', false),
  ('run_unit_tests',         'global', 2, 'Run test suite in sandbox',                    'execute_sandboxed_code', false),
  ('apply_db_migration',     'global', 3, 'Apply SQL migration to PostgreSQL',            'execute_sandboxed_code', true),
  ('write_memory_file',      'global', 3, 'Write to _context/ memory store',             NULL,                     true),
  ('create_keycloak_user',   'global', 3, 'Create user in Keycloak realm',               NULL,                     true),
  ('trigger_tekton_pipeline','global', 4, 'Trigger Tekton CI/CD pipeline',               NULL,                     true),
  ('oc_apply_manifest',      'global', 4, 'Apply Kubernetes manifest to cluster',         NULL,                     true),
  ('promote_to_production',  'global', 4, 'Promote image to production',                 NULL,                     true)
ON CONFLICT (name) DO NOTHING;
EOSQL

echo "==> Bootstrapping talent_db..."
psql -d talent_db << 'EOSQL'
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS candidates (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  keycloak_sub    TEXT        UNIQUE NOT NULL,
  full_name       TEXT        NOT NULL,
  email           TEXT,
  phone           TEXT,
  location        TEXT,
  source          TEXT        DEFAULT 'direct',
  bench_status    TEXT        DEFAULT 'available',
  evalos_passport_id TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS skills (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT UNIQUE NOT NULL,
  category    TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS candidate_skills (
  candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
  skill_id     UUID REFERENCES skills(id) ON DELETE CASCADE,
  proficiency  INT  CHECK (proficiency BETWEEN 1 AND 5),
  endorsed_by  TEXT,
  PRIMARY KEY (candidate_id, skill_id)
);

CREATE TABLE IF NOT EXISTS assessments (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id    UUID        REFERENCES candidates(id),
  evalos_session  TEXT,
  score           DECIMAL(5,2),
  passed          BOOLEAN,
  trace_id        TEXT,
  assessed_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  title        TEXT        NOT NULL,
  client       TEXT,
  description  TEXT,
  skills_req   JSONB,
  status       TEXT        DEFAULT 'open',
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS placements (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID        REFERENCES candidates(id),
  job_id        UUID        REFERENCES jobs(id),
  match_score   DECIMAL(5,2),
  trace_id      TEXT,
  status        TEXT        DEFAULT 'proposed',
  approved_by   TEXT,
  placed_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS teams (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  client      TEXT,
  description TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS team_members (
  team_id      UUID REFERENCES teams(id) ON DELETE CASCADE,
  candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
  role         TEXT,
  joined_at    TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (team_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS passports (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID        REFERENCES candidates(id) UNIQUE,
  badges        JSONB       DEFAULT '[]',
  cert_hashes   JSONB       DEFAULT '[]',
  last_updated  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cand_bench_idx    ON candidates(bench_status);
CREATE INDEX IF NOT EXISTS assess_cand_idx   ON assessments(candidate_id, assessed_at);
CREATE INDEX IF NOT EXISTS place_cand_idx    ON placements(candidate_id, status);
EOSQL

echo "==> Bootstrapping sit_db..."
psql -d sit_db << 'EOSQL'
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS learners (
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

CREATE TABLE IF NOT EXISTS courses (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code            TEXT UNIQUE NOT NULL,
  title           TEXT NOT NULL,
  tvet_level      TEXT,
  duration_weeks  INT,
  delivery        TEXT DEFAULT 'blended'
);

CREATE TABLE IF NOT EXISTS enrollments (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id  UUID        REFERENCES learners(id),
  course_id   UUID        REFERENCES courses(id),
  enrolled_at TIMESTAMPTZ DEFAULT now(),
  status      TEXT        DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS exam_bookings (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id     UUID        REFERENCES enrollments(id),
  evalos_session_id TEXT,
  booked_at         TIMESTAMPTZ DEFAULT now(),
  status            TEXT        DEFAULT 'scheduled'
);

CREATE TABLE IF NOT EXISTS credentials (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id      UUID        REFERENCES learners(id),
  course_id       UUID        REFERENCES courses(id),
  issued_at       TIMESTAMPTZ DEFAULT now(),
  cert_hash       TEXT        NOT NULL,
  qr_token        TEXT        UNIQUE,
  talent_node_id  TEXT
);

CREATE TABLE IF NOT EXISTS professional_bookings (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id        UUID        REFERENCES learners(id),
  professional_id  TEXT        NOT NULL,
  service_type     TEXT,
  scheduled_at     TIMESTAMPTZ,
  commission_pct   DECIMAL(5,2) DEFAULT 20.0,
  status           TEXT        DEFAULT 'pending',
  webrtc_room_id   TEXT
);

CREATE TABLE IF NOT EXISTS membership_subscriptions (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id  UUID        REFERENCES learners(id),
  tier        TEXT        NOT NULL,
  starts_at   TIMESTAMPTZ,
  expires_at  TIMESTAMPTZ,
  qr_token    TEXT        UNIQUE,
  active      BOOLEAN     DEFAULT true
);

CREATE TABLE IF NOT EXISTS ecitizen_cases (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  citizen_id   UUID        REFERENCES learners(id),
  service      TEXT        NOT NULL,
  status       TEXT        DEFAULT 'open',
  n8n_exec_id  TEXT,
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS enroll_learner_idx   ON enrollments(learner_id);
CREATE INDEX IF NOT EXISTS cred_learner_idx     ON credentials(learner_id);
CREATE INDEX IF NOT EXISTS cred_qr_idx          ON credentials(qr_token);
CREATE INDEX IF NOT EXISTS ecitizen_status_idx  ON ecitizen_cases(citizen_id, status);
CREATE INDEX IF NOT EXISTS membership_active_idx ON membership_subscriptions(learner_id, active);
EOSQL

echo "==> Bootstrapping ford_members_db..."
psql -d ford_members_db << 'EOSQL'
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS members_pii (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  id_hash         TEXT        UNIQUE NOT NULL,
  phone_hash      TEXT        NOT NULL,
  ward_code       TEXT        NOT NULL,
  constituency    TEXT,
  county          TEXT,
  consent_at      TIMESTAMPTZ NOT NULL,
  otp_verified    BOOLEAN     DEFAULT false,
  status          TEXT        DEFAULT 'pending',
  flagged_reason  TEXT,
  agent_id        TEXT,
  fabric_tx_id    TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_velocity (
  agent_id         TEXT        NOT NULL,
  window_start     TIMESTAMPTZ NOT NULL,
  registrations    INT         DEFAULT 0,
  verified_count   INT         DEFAULT 0,
  flagged_count    INT         DEFAULT 0,
  PRIMARY KEY (agent_id, window_start)
);

CREATE TABLE IF NOT EXISTS primary_ballots (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  ballot_token    TEXT        UNIQUE NOT NULL,
  ward_code       TEXT        NOT NULL,
  seat_code       TEXT        NOT NULL,
  cast_at         TIMESTAMPTZ,
  status          TEXT        DEFAULT 'pending',
  fabric_tx_id    TEXT
);

CREATE INDEX IF NOT EXISTS members_status_idx  ON members_pii(status, ward_code);
CREATE INDEX IF NOT EXISTS members_agent_idx   ON members_pii(agent_id, created_at);
CREATE INDEX IF NOT EXISTS ballot_ward_idx     ON primary_ballots(ward_code, seat_code, status);
EOSQL

echo "==> Creating application DB users..."
psql -d ar_db          -c "CREATE USER ar_app     WITH PASSWORD '$AR_PASS';     GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ar_app;     GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ar_app;" 2>&1 || echo "ar_app may exist"
psql -d talent_db      -c "CREATE USER talent_app WITH PASSWORD '$TALENT_PASS'; GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO talent_app; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO talent_app;" 2>&1 || echo "talent_app may exist"
psql -d sit_db         -c "CREATE USER sit_app    WITH PASSWORD '$SIT_PASS';    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sit_app;    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sit_app;" 2>&1 || echo "sit_app may exist"
psql -d ford_members_db -c "CREATE USER ford_app  WITH PASSWORD '$FORD_PASS';   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ford_app;   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ford_app;" 2>&1 || echo "ford_app may exist"

echo "==> All done. Verifying databases..."
psql -d i3_platform -c "SELECT datname FROM pg_database WHERE datname IN ('ar_db','talent_db','sit_db','ford_members_db') ORDER BY datname;"
