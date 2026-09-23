-- ============================================================
-- Migration: 007_integrity_scoring.sql
-- EvalOS Phase 1: Adds composable integrity scoring columns to
--   quiz_attempts and creates the integrity_events log table
--   and the multi-agent evaluation reports tables.
--
-- Source: §5 Layer 1, §7.5, §8 of ARCH-EVALOS-2026-V2
-- HC-4: tenant_id propagated on all new tables.
-- ============================================================

BEGIN;

-- ── 1. Integrity scoring columns on quiz_attempts ────────────────────────────
--   identity_score      : confidence the person is who they claim (0–100)
--   behavior_score      : deviation from expected interaction patterns (0–100)
--   integrity_confidence: aggregate copy/tab/AI-gen signal (0–100)
--   trust_score         : composite feeding the human-review queue (0–100)
--   device_fingerprint  : FingerprintJS visitor ID bound at session start
--   requires_review     : true when trust_score drops below threshold (< 60)

ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS identity_score       NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS behavior_score       NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS integrity_confidence NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS trust_score          NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS device_fingerprint   TEXT,
  ADD COLUMN IF NOT EXISTS requires_review      BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_attempts_requires_review
  ON quiz_attempts (requires_review) WHERE requires_review = TRUE;

CREATE INDEX IF NOT EXISTS idx_attempts_trust_score
  ON quiz_attempts (trust_score);

-- ── 2. Integrity Event Log ────────────────────────────────────────────────────
--   Stores individual integrity signals with their raw value for
--   explainability — feeds the Trust Score computation.
CREATE TABLE IF NOT EXISTS integrity_events (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  attempt_id    UUID NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
  student_id    TEXT NOT NULL,
  event_type    TEXT NOT NULL
    CHECK (event_type IN (
      'focus_lost','tab_switch','fullscreen_exit','clipboard_copy',
      'clipboard_paste','devtools_open','secondary_monitor',
      'keyboard_anomaly','ai_content_flag','identity_mismatch',
      'device_change','inactivity_timeout'
    )),
  severity      SMALLINT NOT NULL DEFAULT 1 CHECK (severity BETWEEN 1 AND 3),
  -- 1=low, 2=medium, 3=high
  raw_signal    JSONB NOT NULL DEFAULT '{}',
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_integrity_events_tenant    ON integrity_events (tenant_id);
CREATE INDEX IF NOT EXISTS idx_integrity_events_attempt   ON integrity_events (attempt_id);
CREATE INDEX IF NOT EXISTS idx_integrity_events_student   ON integrity_events (student_id);
CREATE INDEX IF NOT EXISTS idx_integrity_events_type      ON integrity_events (event_type);

ALTER TABLE integrity_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS integrity_events_tenant_isolation ON integrity_events;
CREATE POLICY integrity_events_tenant_isolation ON integrity_events
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 3. Multi-Agent Evaluation Reports ────────────────────────────────────────
--   Stores per-agent scoring outputs from the evaluation pipeline.
--   agent_type examples: CODE_EXAMINER, ARCHITECT, ADVERSARIAL_QA,
--                        CRITIC, AGGREGATOR, TUTOR, INTEGRITY
CREATE TABLE IF NOT EXISTS evaluation_agent_reports (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  attempt_id       UUID REFERENCES quiz_attempts(id) ON DELETE CASCADE,
  session_id       UUID REFERENCES assessment_sessions(id) ON DELETE CASCADE,
  agent_type       VARCHAR(64) NOT NULL,
  score_awarded    NUMERIC(5,2) NOT NULL DEFAULT 0,
  max_score        NUMERIC(5,2) NOT NULL DEFAULT 100,
  findings_summary TEXT,
  detailed_metrics JSONB NOT NULL DEFAULT '{}',
  model_used       TEXT,
  latency_ms       INT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- At least one of attempt_id or session_id must be set
  CONSTRAINT chk_agent_report_ref CHECK (
    attempt_id IS NOT NULL OR session_id IS NOT NULL
  )
);

CREATE INDEX IF NOT EXISTS idx_agent_reports_tenant   ON evaluation_agent_reports (tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_reports_attempt  ON evaluation_agent_reports (attempt_id);
CREATE INDEX IF NOT EXISTS idx_agent_reports_session  ON evaluation_agent_reports (session_id);
CREATE INDEX IF NOT EXISTS idx_agent_reports_type     ON evaluation_agent_reports (agent_type);

ALTER TABLE evaluation_agent_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS evaluation_agent_reports_tenant_isolation ON evaluation_agent_reports;
CREATE POLICY evaluation_agent_reports_tenant_isolation ON evaluation_agent_reports
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 4. Assessment Final Results ───────────────────────────────────────────────
--   Denormalized result record with skill vector and credential hash.
CREATE TABLE IF NOT EXISTS assessment_final_results (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  attempt_id              UUID UNIQUE REFERENCES quiz_attempts(id) ON DELETE CASCADE,
  session_id              UUID UNIQUE REFERENCES assessment_sessions(id) ON DELETE CASCADE,
  total_score             NUMERIC(5,2) NOT NULL DEFAULT 0,
  performance_band        VARCHAR(32)
    CHECK (performance_band IN (
      'EXCEPTIONAL','PRODUCTION_READY','EMERGING','DEVELOPING','NOT_READY'
    )),
  recommendation_verdict  VARCHAR(64),
  skill_vector            JSONB NOT NULL DEFAULT '{}',
  certificate_hash        VARCHAR(128),
  webhook_dispatched_at   TIMESTAMPTZ,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_final_result_ref CHECK (
    attempt_id IS NOT NULL OR session_id IS NOT NULL
  )
);

CREATE INDEX IF NOT EXISTS idx_final_results_tenant  ON assessment_final_results (tenant_id);
CREATE INDEX IF NOT EXISTS idx_final_results_attempt ON assessment_final_results (attempt_id);
CREATE INDEX IF NOT EXISTS idx_final_results_session ON assessment_final_results (session_id);

ALTER TABLE assessment_final_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS assessment_final_results_tenant_isolation ON assessment_final_results;
CREATE POLICY assessment_final_results_tenant_isolation ON assessment_final_results
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 5. Admissions Webhook Log ────────────────────────────────────────────────
--   Audit trail for inbound + outbound admissions webhook events.
CREATE TABLE IF NOT EXISTS admissions_webhook_log (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  direction        VARCHAR(8) NOT NULL CHECK (direction IN ('inbound','outbound')),
  event_type       VARCHAR(64) NOT NULL,
  payload          JSONB NOT NULL DEFAULT '{}',
  applicant_id     TEXT,
  attempt_id       UUID,
  status_code      INT,
  error_message    TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_log_tenant     ON admissions_webhook_log (tenant_id);
CREATE INDEX IF NOT EXISTS idx_webhook_log_direction  ON admissions_webhook_log (direction);
CREATE INDEX IF NOT EXISTS idx_webhook_log_applicant  ON admissions_webhook_log (applicant_id);
CREATE INDEX IF NOT EXISTS idx_webhook_log_event      ON admissions_webhook_log (event_type);

ALTER TABLE admissions_webhook_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS admissions_webhook_log_tenant_isolation ON admissions_webhook_log;
CREATE POLICY admissions_webhook_log_tenant_isolation ON admissions_webhook_log
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

COMMIT;
