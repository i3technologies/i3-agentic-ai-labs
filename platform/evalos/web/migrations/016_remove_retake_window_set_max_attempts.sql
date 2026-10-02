-- ============================================================
-- Migration: 016_remove_retake_window_set_max_attempts.sql
--
-- 1. Remove the 48-hour retake window constraint — students may
--    retake an exam at any time (no deadline pressure).
-- 2. Enforce max_attempts = 3 on every published exam.
--    Each student gets 1 initial attempt + 2 retakes.
-- 3. Nullify retake_window_hours on all existing rows so the
--    application column can be safely dropped or ignored.
--
-- Safe to re-run (idempotent via SET … WHERE clause).
-- ============================================================

BEGIN;

-- ── 1. Clear retake_window_hours on all exams ───────────────────────────────
-- No 48-hour retake window; students may retake whenever they choose.
UPDATE exams
  SET retake_window_hours = NULL
  WHERE retake_window_hours IS NOT NULL;

-- ── 2. Set max_attempts = 3 on every published exam ────────────────────────
-- 1 initial attempt + 2 retakes = 3 total chances per exam.
UPDATE exams
  SET max_attempts = 3
  WHERE max_attempts IS DISTINCT FROM 3;

-- ── 3. Update the default for new exams ────────────────────────────────────
ALTER TABLE exams
  ALTER COLUMN max_attempts SET DEFAULT 3;

COMMENT ON COLUMN exams.retake_window_hours IS
  'Deprecated — no longer enforced. Retakes have no time-based window; '
  'students are limited only by max_attempts (3).';

COMMIT;
