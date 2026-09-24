-- ============================================================
-- Migration 003: EvalOS saga status values + Engage DLQ table
-- Applies to: evalos_db, engage_db (adjust connection accordingly)
-- Idempotent: uses IF NOT EXISTS / DO NOTHING guards.
-- ============================================================

-- ── evalos_db ────────────────────────────────────────────────────────────────

-- The quiz_attempts.status column used a freeform varchar.
-- Add the two new saga states so CHECK constraints (if any) accept them,
-- and so the existing partial index covers retryable attempts efficiently.

-- If the column has an explicit CHECK constraint, extend it; otherwise this
-- comment is informational and the UPDATE/INSERT in application code is sufficient.
-- Uncomment and adapt if your schema defines: CONSTRAINT quiz_attempts_status_check CHECK (status IN (...))
-- ALTER TABLE quiz_attempts DROP CONSTRAINT IF EXISTS quiz_attempts_status_check;
-- ALTER TABLE quiz_attempts ADD CONSTRAINT quiz_attempts_status_check
--   CHECK (status IN ('in_progress','grading','submitted','grading_failed','graded'));

-- Index on retryable attempts — lets the start/ route efficiently exclude grading_failed
-- from new-attempt eligibility checks.
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_retryable
  ON quiz_attempts (exam_id, student_id, status)
  WHERE status IN ('in_progress', 'grading', 'grading_failed');

-- Index on submitted/graded for prerequisite + pass-rate queries.
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_completed
  ON quiz_attempts (exam_id, student_id, passed)
  WHERE status IN ('submitted', 'graded');

-- ── engage_db ─────────────────────────────────────────────────────────────────

-- Dead-letter queue tracking table for engage.ai-personalize.dlq messages.
-- The Kafka DLQ consumer (P3) writes here so operations teams have a queryable
-- view of failed personalisation jobs without needing Kafka CLI access.

CREATE TABLE IF NOT EXISTS ai_personalise_dlq (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL,                          -- HC-4
    job_id          TEXT        NOT NULL,
    send_job_id     TEXT        NOT NULL,
    campaign_id     INTEGER,
    channel         TEXT        NOT NULL,
    failure_reason  TEXT        NOT NULL,
    original_topic  TEXT        NOT NULL DEFAULT 'engage.ai-personalize',
    payload         JSONB       NOT NULL DEFAULT '{}',
    retry_count     INTEGER     NOT NULL DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'pending'         -- pending | retried | discarded
        CHECK (status IN ('pending', 'retried', 'discarded')),
    failed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ai_personalise_dlq_tenant_status
  ON ai_personalise_dlq (tenant_id, status, failed_at DESC);

-- RLS: operations team queries must be tenant-scoped.
ALTER TABLE ai_personalise_dlq ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'ai_personalise_dlq' AND policyname = 'tenant_isolation'
  ) THEN
    CREATE POLICY tenant_isolation ON ai_personalise_dlq
      USING (tenant_id = current_setting('app.tenant_id')::uuid);
  END IF;
END
$$;
