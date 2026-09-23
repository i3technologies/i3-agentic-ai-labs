-- ============================================================
-- Migration: 005_add_tenant_id.sql
-- HC-4 Remediation: adds tenant_id UUID NOT NULL to EvalOS core
-- tables and enables Row-Level Security.
--
-- Affected tables:
--   questions         (question bank)
--   exams             (exam definitions)
--   quiz_attempts     (student attempt records)
--   attempt_answers   (per-question attempt detail)
--   user_weaknesses   (adaptive learning map)
--   sandbox_results   (code execution results)
--   ai_interview_evaluations  (from migration 003)
--
-- Default tenant: 00000000-0000-0000-0000-000000000002
--   (EvalOS platform tenant — update per-row once real tenant
--    mapping is known)
--
-- Safe to run multiple times (uses IF NOT EXISTS / IF NOT EXISTS).
-- ============================================================

BEGIN;

-- ── 1. questions ─────────────────────────────────────────────────────────────
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_questions_tenant ON questions (tenant_id);

ALTER TABLE questions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS questions_tenant_isolation ON questions;
CREATE POLICY questions_tenant_isolation ON questions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 2. exams ──────────────────────────────────────────────────────────────────
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_exams_tenant ON exams (tenant_id);

ALTER TABLE exams ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS exams_tenant_isolation ON exams;
CREATE POLICY exams_tenant_isolation ON exams
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 3. quiz_attempts ──────────────────────────────────────────────────────────
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_attempts_tenant ON quiz_attempts (tenant_id);

ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS quiz_attempts_tenant_isolation ON quiz_attempts;
CREATE POLICY quiz_attempts_tenant_isolation ON quiz_attempts
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 4. attempt_answers ────────────────────────────────────────────────────────
ALTER TABLE attempt_answers
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_answers_tenant ON attempt_answers (tenant_id);

ALTER TABLE attempt_answers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS attempt_answers_tenant_isolation ON attempt_answers;
CREATE POLICY attempt_answers_tenant_isolation ON attempt_answers
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 5. user_weaknesses ────────────────────────────────────────────────────────
ALTER TABLE user_weaknesses
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_weaknesses_tenant ON user_weaknesses (tenant_id);

ALTER TABLE user_weaknesses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_weaknesses_tenant_isolation ON user_weaknesses;
CREATE POLICY user_weaknesses_tenant_isolation ON user_weaknesses
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 6. sandbox_results ───────────────────────────────────────────────────────
ALTER TABLE sandbox_results
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_sandbox_tenant ON sandbox_results (tenant_id);

ALTER TABLE sandbox_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sandbox_results_tenant_isolation ON sandbox_results;
CREATE POLICY sandbox_results_tenant_isolation ON sandbox_results
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 7. ai_interview_evaluations (from migration 003) ─────────────────────────
ALTER TABLE ai_interview_evaluations
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_aie_tenant ON ai_interview_evaluations (tenant_id);

ALTER TABLE ai_interview_evaluations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_interview_evaluations_tenant_isolation ON ai_interview_evaluations;
CREATE POLICY ai_interview_evaluations_tenant_isolation ON ai_interview_evaluations
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 8. ai_interview_questions (from migration 003) ───────────────────────────
-- This table stores admin-managed content, not per-student data.
-- Tenant isolation is still required for multi-tenant exam platforms.
ALTER TABLE ai_interview_questions
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

CREATE INDEX IF NOT EXISTS idx_aiq_tenant ON ai_interview_questions (tenant_id);

ALTER TABLE ai_interview_questions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_interview_questions_tenant_isolation ON ai_interview_questions;
CREATE POLICY ai_interview_questions_tenant_isolation ON ai_interview_questions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 9. Grant usage on app.tenant_id setting ──────────────────────────────────
-- Ensure the application role can SET LOCAL app.tenant_id
-- (replace 'evalos_app' with the actual DB role used by the service)
-- GRANT SET ON PARAMETER app.tenant_id TO evalos_app;

COMMIT;

-- ── Post-migration checklist ──────────────────────────────────────────────────
-- After applying:
-- 1. Update platform/evalos/web/src/app/api/exam/[examId]/start/route.ts
--    and submit/route.ts to call:
--      await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
--    before any table query (same pattern as Engage contacts/route.ts).
-- 2. Backfill tenant_id on existing rows if real tenant mapping is known.
-- 3. Run: SELECT COUNT(*) FROM questions WHERE tenant_id = '00000000-0000-0000-0000-000000000002'
--    to confirm all rows were migrated.
