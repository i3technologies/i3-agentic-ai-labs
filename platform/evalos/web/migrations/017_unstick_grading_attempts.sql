-- ============================================================
-- Migration: 017_unstick_grading_attempts.sql
--
-- Rescue attempts that were left in 'grading' or 'in_progress'
-- status due to pod restarts or grading-service unavailability.
--
-- Behaviour:
--   • Any attempt stuck in 'grading' for more than 5 minutes is
--     reset to 'grading_failed' so the student can resubmit.
--     The submit route now includes an inline fallback grader,
--     so resubmission will always produce a score even when the
--     external grading service is unreachable.
--   • Attempts stuck in 'in_progress' for more than 24 hours are
--     also reset to 'grading_failed' (timed-out sessions).
--
-- Safe to re-run (idempotent — only touches rows matching the
-- time-based conditions).
-- ============================================================

BEGIN;

-- ── 1. Rescue stuck 'grading' attempts (pod died mid-grade) ────────────────
UPDATE quiz_attempts
  SET status = 'grading_failed',
      proctor_flags = proctor_flags || '{"grading_error":"rescued by migration 017 — pod restart during grading","failed_at":"now"}'::jsonb
  WHERE status = 'grading'
    AND submitted_at < NOW() - INTERVAL '5 minutes';

-- ── 2. Rescue timed-out 'in_progress' attempts (> 24 hours old) ────────────
-- These are orphaned sessions where the student never submitted.
-- Marking them grading_failed lets the student resubmit and get a score.
UPDATE quiz_attempts
  SET status = 'grading_failed',
      proctor_flags = proctor_flags || '{"grading_error":"rescued by migration 017 — session expired without submission","failed_at":"now"}'::jsonb
  WHERE status = 'in_progress'
    AND started_at < NOW() - INTERVAL '24 hours';

COMMIT;
