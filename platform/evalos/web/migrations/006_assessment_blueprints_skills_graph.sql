-- ============================================================
-- Migration: 006_assessment_blueprints_skills_graph.sql
-- EvalOS Phase 1: Assessment Blueprints, Challenge Modules,
--   Skills Graph nodes, and Candidate Skill Evidence tables.
--
-- Source: §7.5 of EvalOS Technical Implementation Guide
--         (ARCH-EVALOS-2026-V2)
-- HC-4: tenant_id UUID NOT NULL on every table.
-- ============================================================

BEGIN;

-- ── Assessment Blueprints ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assessment_blueprints (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  slug                 VARCHAR(64) UNIQUE NOT NULL,
  title                VARCHAR(255) NOT NULL,
  track_type           VARCHAR(32) NOT NULL
    CHECK (track_type IN ('ADMISSIONS_FILTER','CERT_PREP_SIM','ENTERPRISE_BENCHMARK','CODING_LAB')),
  target_role          VARCHAR(64),
  time_limit_minutes   INT NOT NULL DEFAULT 60,
  rubric_config        JSONB NOT NULL DEFAULT '{}',
  adaptive             BOOLEAN NOT NULL DEFAULT FALSE,
  created_by           TEXT NOT NULL DEFAULT 'system',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blueprints_tenant     ON assessment_blueprints (tenant_id);
CREATE INDEX IF NOT EXISTS idx_blueprints_track_type ON assessment_blueprints (track_type);

ALTER TABLE assessment_blueprints ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS assessment_blueprints_tenant_isolation ON assessment_blueprints;
CREATE POLICY assessment_blueprints_tenant_isolation ON assessment_blueprints
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Challenge Modules (practical/coding) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS challenge_modules (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  blueprint_id         UUID REFERENCES assessment_blueprints(id) ON DELETE CASCADE,
  title                VARCHAR(255) NOT NULL,
  problem_spec_markdown TEXT NOT NULL,
  container_image_ref  VARCHAR(255) NOT NULL DEFAULT 'evalos/sandbox:latest',
  starter_repo_url     VARCHAR(512),
  test_suite_repo_url  VARCHAR(512),
  resource_limits      JSONB NOT NULL DEFAULT '{"cpu":"1.0","memory_mb":1024,"network_egress":false}',
  skill_tags           TEXT[] NOT NULL DEFAULT '{}',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_challenge_modules_tenant    ON challenge_modules (tenant_id);
CREATE INDEX IF NOT EXISTS idx_challenge_modules_blueprint ON challenge_modules (blueprint_id);

ALTER TABLE challenge_modules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS challenge_modules_tenant_isolation ON challenge_modules;
CREATE POLICY challenge_modules_tenant_isolation ON challenge_modules
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Assessment Sessions (blueprint-driven, supplements quiz_attempts) ─────────
-- Note: quiz_attempts remains the primary attempt table for MCQ/certification.
-- assessment_sessions is the richer session record for blueprint-driven labs.
CREATE TABLE IF NOT EXISTS assessment_sessions (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  candidate_id         VARCHAR(128) NOT NULL,
  blueprint_id         UUID REFERENCES assessment_blueprints(id),
  status               VARCHAR(32) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING','IN_PROGRESS','SUBMITTED','GRADING','GRADED','FLAGGED','VOIDED')),
  integrity_confidence NUMERIC(5,2),
  identity_score       NUMERIC(5,2),
  behavior_score       NUMERIC(5,2),
  trust_score          NUMERIC(5,2),
  sandbox_endpoint     VARCHAR(255),
  device_fingerprint   TEXT,
  session_started_at   TIMESTAMPTZ,
  submitted_at         TIMESTAMPTZ,
  expires_at           TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '4 hours'),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_asessions_tenant       ON assessment_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_asessions_candidate    ON assessment_sessions (candidate_id);
CREATE INDEX IF NOT EXISTS idx_asessions_blueprint    ON assessment_sessions (blueprint_id);
CREATE INDEX IF NOT EXISTS idx_asessions_status       ON assessment_sessions (status);

ALTER TABLE assessment_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS assessment_sessions_tenant_isolation ON assessment_sessions;
CREATE POLICY assessment_sessions_tenant_isolation ON assessment_sessions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Skills Graph — Nodes ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS skill_nodes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  name        VARCHAR(128) NOT NULL,
  parent_id   UUID REFERENCES skill_nodes(id) ON DELETE SET NULL,
  level       VARCHAR(32) NOT NULL DEFAULT 'skill'
    CHECK (level IN ('technology','competency','skill','sub-skill')),
  description TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, name, level)
);

CREATE INDEX IF NOT EXISTS idx_skill_nodes_tenant    ON skill_nodes (tenant_id);
CREATE INDEX IF NOT EXISTS idx_skill_nodes_parent    ON skill_nodes (parent_id);

ALTER TABLE skill_nodes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS skill_nodes_tenant_isolation ON skill_nodes;
CREATE POLICY skill_nodes_tenant_isolation ON skill_nodes
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Candidate Skill Evidence ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candidate_skill_evidence (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  candidate_id  VARCHAR(128) NOT NULL,
  skill_id      UUID REFERENCES skill_nodes(id) ON DELETE CASCADE,
  proficiency   NUMERIC(5,2) NOT NULL DEFAULT 0.0 CHECK (proficiency BETWEEN 0 AND 100),
  evidence_type VARCHAR(32) NOT NULL DEFAULT 'exam'
    CHECK (evidence_type IN ('exam','lab','interview','certification','manual')),
  evidence_ref  UUID,          -- FK to quiz_attempts.id or assessment_sessions.id
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skill_evidence_tenant    ON candidate_skill_evidence (tenant_id);
CREATE INDEX IF NOT EXISTS idx_skill_evidence_candidate ON candidate_skill_evidence (candidate_id);
CREATE INDEX IF NOT EXISTS idx_skill_evidence_skill     ON candidate_skill_evidence (skill_id);

ALTER TABLE candidate_skill_evidence ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS candidate_skill_evidence_tenant_isolation ON candidate_skill_evidence;
CREATE POLICY candidate_skill_evidence_tenant_isolation ON candidate_skill_evidence
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── updated_at trigger for blueprints ────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_blueprints_updated ON assessment_blueprints;
CREATE TRIGGER trg_blueprints_updated
  BEFORE UPDATE ON assessment_blueprints
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
