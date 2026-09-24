-- ============================================================
-- Migration: 004_ai_interview_tenant_id.sql
-- HC-4 Remediation: adds tenant_id UUID NOT NULL to the two
-- EvalOS interview tables introduced in 003_ai_features.sql.
--
-- Applied after: 003_ai_features.sql
-- Idempotent: YES (uses IF NOT EXISTS / ALTER … IF NOT EXISTS)
-- ============================================================

-- ── 1. ai_interview_evaluations ─────────────────────────────

-- Add tenant_id column with a temporary DEFAULT so existing rows
-- are backfilled immediately. The DEFAULT is dropped after backfill.
ALTER TABLE ai_interview_evaluations
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';  -- HC-4 sentinel

-- Index for RLS scan performance
CREATE INDEX IF NOT EXISTS idx_ai_eval_tenant
  ON ai_interview_evaluations (tenant_id);

-- RLS policy — mirrors the pattern used across all i3 EvalOS tables
ALTER TABLE ai_interview_evaluations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_interview_evaluations_tenant_isolation
  ON ai_interview_evaluations;

CREATE POLICY ai_interview_evaluations_tenant_isolation
  ON ai_interview_evaluations
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

COMMENT ON COLUMN ai_interview_evaluations.tenant_id IS
  'HC-4: Owning tenant UUID. NOT NULL. Protected by RLS policy ai_interview_evaluations_tenant_isolation.';

-- ── 2. ai_interview_questions ───────────────────────────────

ALTER TABLE ai_interview_questions
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';  -- HC-4 sentinel

CREATE INDEX IF NOT EXISTS idx_ai_iq_tenant
  ON ai_interview_questions (tenant_id);

ALTER TABLE ai_interview_questions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_interview_questions_tenant_isolation
  ON ai_interview_questions;

CREATE POLICY ai_interview_questions_tenant_isolation
  ON ai_interview_questions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

COMMENT ON COLUMN ai_interview_questions.tenant_id IS
  'HC-4: Owning tenant UUID. NOT NULL. Protected by RLS policy ai_interview_questions_tenant_isolation.';

-- ── Backfill note ────────────────────────────────────────────
-- All existing rows receive the sentinel value above.
-- Before going live, update rows to their real tenant UUID:
--   UPDATE ai_interview_evaluations
--     SET tenant_id = '<real-uuid>'
--    WHERE tenant_id = '00000000-0000-0000-0000-000000000002';
--   UPDATE ai_interview_questions
--     SET tenant_id = '<real-uuid>'
--    WHERE tenant_id = '00000000-0000-0000-0000-000000000002';
-- Then:
--   ALTER TABLE ai_interview_evaluations ALTER COLUMN tenant_id DROP DEFAULT;
--   ALTER TABLE ai_interview_questions   ALTER COLUMN tenant_id DROP DEFAULT;
