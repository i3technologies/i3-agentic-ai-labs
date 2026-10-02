-- ============================================================
-- Migration: 019_certificates_pass_threshold.sql
--
-- 1. Add pass_threshold column to certificates so every
--    certificate PDF download reflects the actual threshold
--    that applied at the time of the exam (e.g. 68% for Sets 1–6,
--    90% for Set 7), rather than always showing 90%.
--
-- 2. Add a UNIQUE constraint on certificates(attempt_id) so the
--    ON CONFLICT (attempt_id) DO UPDATE in the certificate API
--    route works correctly — prevents duplicate cert rows from
--    being created if the button is clicked multiple times.
--
-- 3. Backfill pass_threshold from the joined exams row for all
--    existing certificate rows that have NULL (pre-migration certs).
--
-- Safe to re-run (ADD COLUMN IF NOT EXISTS / IF NOT EXISTS index).
-- ============================================================

BEGIN;

-- ── 1. Add pass_threshold column ─────────────────────────────────────────────
ALTER TABLE certificates
  ADD COLUMN IF NOT EXISTS pass_threshold NUMERIC(5,2) NOT NULL DEFAULT 90.0;

-- ── 2. Backfill from the exam for existing certs ──────────────────────────────
UPDATE certificates c
SET pass_threshold = COALESCE(e.pass_threshold, e.passing_score, 90.0)
FROM quiz_attempts qa
JOIN exams e ON e.id = qa.exam_id
WHERE qa.id = c.attempt_id
  AND c.pass_threshold = 90.0;  -- only update the default-filled rows

-- ── 3. Add UNIQUE constraint on attempt_id ────────────────────────────────────
-- Required for ON CONFLICT (attempt_id) in the certificate issue route.
-- Drop first in case a partial index already exists from an earlier run.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'certificates'::regclass
      AND conname  = 'certificates_attempt_id_key'
  ) THEN
    ALTER TABLE certificates ADD CONSTRAINT certificates_attempt_id_key UNIQUE (attempt_id);
  END IF;
END;
$$;

-- ── 4. graded_at column on quiz_attempts (safety backfill) ───────────────────
-- The submit route now writes graded_at = NOW() on every successful grade.
-- Backfill existing submitted/graded rows that have NULL graded_at from
-- submitted_at (best approximation — they were graded near submission time).
UPDATE quiz_attempts
  SET graded_at = COALESCE(submitted_at, started_at, NOW())
  WHERE status IN ('submitted', 'graded')
    AND graded_at IS NULL;

COMMIT;
