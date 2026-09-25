-- Migration: V003__add_grading_statuses.sql
-- Adds 'grading' and 'grading_failed' to the quiz_attempts.status CHECK constraint.
-- Without this, the submit route UPDATE that sets status='grading' is rejected by
-- the DB and the attempt stays stuck in 'in_progress' forever (seen as "Pending" by students).
--
-- Safe to run on a live database — DROP CONSTRAINT / ADD CONSTRAINT is a metadata-only
-- change in PostgreSQL and does not rewrite the table.

BEGIN;

-- Step 1: drop the old constraint (name may differ per environment; use pg_constraint to be safe)
DO $$
DECLARE
    v_constraint_name text;
BEGIN
    SELECT conname INTO v_constraint_name
    FROM pg_constraint
    WHERE conrelid = 'quiz_attempts'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%status%in_progress%';

    IF v_constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE quiz_attempts DROP CONSTRAINT %I', v_constraint_name);
    END IF;
END;
$$;

-- Step 2: add the expanded constraint
ALTER TABLE quiz_attempts
    ADD CONSTRAINT quiz_attempts_status_check
    CHECK (status IN (
        'in_progress',
        'grading',
        'grading_failed',
        'submitted',
        'graded',
        'flagged',
        'voided',
        'invalidated'
    ));

COMMIT;
