-- ============================================================
-- Migration: 024_final_state_verification.sql
--
-- Final idempotent state-verification migration.
-- Safe to re-run at any time with no side effects.
--
-- Actions:
--   1. Ensure Set 7 (C1000-207-SET7) is correctly configured.
--   2. Ensure ALL published exams have max_attempts = 3.
--   3. Add 'voided' to quiz_attempts status CHECK if not already
--      present (some DB instances were seeded from the older
--      evalos/schema.sql which used 'invalidated' instead).
--   4. Backfill graded_at on submitted/graded rows where NULL.
--   5. Confirm pass_threshold on certificates table (migration 019
--      column); backfill for any NULL rows.
--   6. Verify certificates table has the UNIQUE constraint on
--      attempt_id (required for ON CONFLICT in certificate route).
-- ============================================================

BEGIN;

-- ── 1. Set 7 exam configuration ───────────────────────────────────────────────
UPDATE exams
  SET max_attempts        = 3,
      pass_threshold      = 90.0,
      retake_window_hours = NULL,
      is_published        = true
  WHERE code = 'C1000-207-SET7';

-- ── 2. All published exams: max_attempts = 3 ─────────────────────────────────
UPDATE exams
  SET max_attempts = 3
  WHERE is_published = true
    AND max_attempts IS DISTINCT FROM 3;

-- ── 3. Add 'voided' to quiz_attempts status CHECK ────────────────────────────
-- The application now sets status = 'voided' for bug-affected attempts.
-- If the database was seeded from the older evalos/schema.sql (which used
-- 'invalidated' instead of 'voided'), the CHECK constraint must be updated.
DO $$
BEGIN
  -- Test whether 'voided' is already permitted by the current CHECK constraint
  -- by attempting a no-op UPDATE on a non-existent row.
  BEGIN
    -- Drop and recreate the constraint to ensure 'voided' is included.
    ALTER TABLE quiz_attempts
      DROP CONSTRAINT IF EXISTS quiz_attempts_status_check;
    ALTER TABLE quiz_attempts
      ADD CONSTRAINT quiz_attempts_status_check
      CHECK (status IN (
        'in_progress', 'grading', 'grading_failed',
        'submitted', 'graded', 'flagged', 'voided', 'invalidated'
      ));
    RAISE NOTICE 'Migration 024: quiz_attempts status CHECK updated to include voided and invalidated.';
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Migration 024: could not update status CHECK — %', SQLERRM;
  END;
END;
$$;

-- ── 4. Backfill graded_at on submitted/graded rows where NULL ─────────────────
UPDATE quiz_attempts
  SET graded_at = COALESCE(submitted_at, started_at, NOW())
  WHERE status IN ('submitted', 'graded')
    AND graded_at IS NULL;

-- ── 5. Ensure pass_threshold column exists on certificates ───────────────────
ALTER TABLE certificates
  ADD COLUMN IF NOT EXISTS pass_threshold NUMERIC(5,2) NOT NULL DEFAULT 90.0;

-- Backfill for any NULL or default-value rows from pre-migration-019 data
UPDATE certificates c
  SET pass_threshold = COALESCE(e.pass_threshold, e.passing_score, 90.0)
  FROM quiz_attempts qa
  JOIN exams e ON e.id = qa.exam_id
  WHERE qa.id = c.attempt_id
    AND c.pass_threshold = 90.0;

-- ── 6. Ensure UNIQUE constraint on certificates(attempt_id) ──────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'certificates'::regclass
      AND conname  = 'certificates_attempt_id_key'
  ) THEN
    ALTER TABLE certificates ADD CONSTRAINT certificates_attempt_id_key UNIQUE (attempt_id);
    RAISE NOTICE 'Migration 024: added UNIQUE constraint on certificates(attempt_id).';
  ELSE
    RAISE NOTICE 'Migration 024: certificates_attempt_id_key already exists — skipped.';
  END IF;
END;
$$;

DO $$
BEGIN
  RAISE NOTICE 'Migration 024: final state verification complete.';
END;
$$;

COMMIT;
