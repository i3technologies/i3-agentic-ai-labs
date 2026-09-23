-- ============================================================
-- Migration: 008_cat_engine.sql
-- EvalOS Phase 2: Computer-Adaptive Testing (CAT) engine tables.
--
-- Implements IRT-based Item Response Theory item calibration and
-- per-session adaptive item selection state tracking.
--
-- Source: §5 Layer 2, §2.3 of ARCH-EVALOS-2026-V2
-- HC-4: tenant_id UUID NOT NULL on all tables.
-- ============================================================

BEGIN;

-- ── IRT Item Parameters ───────────────────────────────────────────────────────
-- 3-parameter logistic model (3PL):
--   a = discrimination  (0.5–3.0; higher = better discriminates ability level)
--   b = difficulty      (-3.0–3.0; logit scale, 0 = average candidate)
--   c = guessing        (0.0–0.35; pseudo-chance for MCQ)
--   d = upper asymptote (default 1.0; lowered if answer key ambiguity)
--
-- Parameters are estimated from operational response data via EM calibration.
-- Initial values are set by content authors; updated by the calibration job.
CREATE TABLE IF NOT EXISTS irt_parameters (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  question_id   UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  a_param       NUMERIC(6,4) NOT NULL DEFAULT 1.0 CHECK (a_param > 0),
  b_param       NUMERIC(6,4) NOT NULL DEFAULT 0.0,
  c_param       NUMERIC(6,4) NOT NULL DEFAULT 0.25 CHECK (c_param BETWEEN 0 AND 0.35),
  d_param       NUMERIC(6,4) NOT NULL DEFAULT 1.0 CHECK (d_param BETWEEN 0.5 AND 1.0),
  -- Calibration metadata
  calibrated_at TIMESTAMPTZ,
  sample_n      INT NOT NULL DEFAULT 0,  -- number of responses used in calibration
  fit_chi2      NUMERIC(8,4),            -- chi-squared fit statistic
  is_calibrated BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_irt_params_tenant   ON irt_parameters (tenant_id);
CREATE INDEX IF NOT EXISTS idx_irt_params_question ON irt_parameters (question_id);

ALTER TABLE irt_parameters ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS irt_parameters_tenant_isolation ON irt_parameters;
CREATE POLICY irt_parameters_tenant_isolation ON irt_parameters
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── CAT Sessions ──────────────────────────────────────────────────────────────
-- One CAT session per quiz_attempt that uses adaptive mode.
-- Tracks the running theta estimate and SE between each item.
CREATE TABLE IF NOT EXISTS cat_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  attempt_id      UUID NOT NULL UNIQUE REFERENCES quiz_attempts(id) ON DELETE CASCADE,
  -- Ability estimate: theta on a standard logit scale (-3 to +3)
  theta           NUMERIC(6,4) NOT NULL DEFAULT 0.0,
  -- Standard error of theta estimate
  theta_se        NUMERIC(6,4) NOT NULL DEFAULT 1.0,
  -- Item selection method
  selection_method VARCHAR(32) NOT NULL DEFAULT 'max_info'
    CHECK (selection_method IN ('max_info','a_stratified','random','shadow_test')),
  -- Stopping rule
  stop_criterion  VARCHAR(32) NOT NULL DEFAULT 'fixed_n'
    CHECK (stop_criterion IN ('fixed_n','se_threshold','min_max')),
  stop_value      NUMERIC(6,4) NOT NULL DEFAULT 20,  -- e.g. 20 items or SE < 0.30
  items_administered INT NOT NULL DEFAULT 0,
  is_complete     BOOLEAN NOT NULL DEFAULT FALSE,
  final_theta     NUMERIC(6,4),
  final_se        NUMERIC(6,4),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cat_sessions_tenant  ON cat_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_cat_sessions_attempt ON cat_sessions (attempt_id);

ALTER TABLE cat_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cat_sessions_tenant_isolation ON cat_sessions;
CREATE POLICY cat_sessions_tenant_isolation ON cat_sessions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── CAT Item Responses ────────────────────────────────────────────────────────
-- Stores each item presented and the candidate's response, plus
-- theta estimate at the time the item was selected (for audit).
CREATE TABLE IF NOT EXISTS cat_item_responses (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  cat_session_id  UUID NOT NULL REFERENCES cat_sessions(id) ON DELETE CASCADE,
  question_id     UUID NOT NULL REFERENCES questions(id),
  item_position   SMALLINT NOT NULL,    -- 1-based order of administration
  theta_before    NUMERIC(6,4) NOT NULL, -- ability estimate when item was selected
  se_before       NUMERIC(6,4) NOT NULL,
  information     NUMERIC(8,6),         -- Fisher information at theta_before
  is_correct      BOOLEAN,
  response_value  JSONB,                -- raw answer value
  time_spent_secs INT,
  theta_after     NUMERIC(6,4),         -- ability estimate after updating
  se_after        NUMERIC(6,4),
  presented_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cat_responses_tenant  ON cat_item_responses (tenant_id);
CREATE INDEX IF NOT EXISTS idx_cat_responses_session ON cat_item_responses (cat_session_id);

ALTER TABLE cat_item_responses ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cat_item_responses_tenant_isolation ON cat_item_responses;
CREATE POLICY cat_item_responses_tenant_isolation ON cat_item_responses
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── updated_at triggers ────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_irt_params_updated ON irt_parameters;
CREATE TRIGGER trg_irt_params_updated
  BEFORE UPDATE ON irt_parameters
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_cat_sessions_updated ON cat_sessions;
CREATE TRIGGER trg_cat_sessions_updated
  BEFORE UPDATE ON cat_sessions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Seed default IRT parameters for all existing active questions ─────────────
-- Uses 1PL (Rasch-like) defaults until calibration data is available.
-- Guard: only seed rows where difficulty is a numeric value (1–5).
INSERT INTO irt_parameters (tenant_id, question_id, a_param, b_param, c_param)
SELECT
  '00000000-0000-0000-0000-000000000002'::uuid,
  id,
  1.0::numeric,
  CASE
    WHEN difficulty ~ '^[1-5]$' THEN
      CASE difficulty::int
        WHEN 1 THEN -1.5
        WHEN 2 THEN -0.5
        WHEN 3 THEN  0.0
        WHEN 4 THEN  0.8
        WHEN 5 THEN  1.5
        ELSE         0.0
      END
    ELSE 0.0
  END::numeric,
  0.25::numeric
FROM questions
WHERE is_active = true
ON CONFLICT (tenant_id, question_id) DO NOTHING;

COMMIT;
