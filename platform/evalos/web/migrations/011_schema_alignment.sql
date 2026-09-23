-- ============================================================
-- Migration: 011_schema_alignment.sql
-- Aligns the exams, quiz_attempts, and questions tables with the
-- column names used throughout the EvalOS Next.js application.
--
-- The base schema (schema.sql) was written with different column
-- names than the app code. This migration adds the missing columns
-- using ADD COLUMN IF NOT EXISTS so it is safe to re-run.
--
-- Changes:
--   exams          → add code, description, duration_minutes,
--                      pass_threshold, max_attempts, randomize_order,
--                      tags, prerequisite_exam_id, tenant_id,
--                      duration_secs (alias)
--   quiz_attempts  → add pct_score, max_score, score,
--                      focus_lost_count, fullscreen_exits,
--                      clipboard_events, tab_switch_events,
--                      proctor_flags, keystroke_entropy, cohort_id,
--                      graded_at, grading columns
--   questions      → add text (alias stem), type (alias question_type),
--                      correct_answers, domain_number, domain_name,
--                      set_number, question_number, ai_generated
-- ============================================================

BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- 1. exams table
-- ═══════════════════════════════════════════════════════════════

-- code: human-readable exam identifier used in app logic (e.g. "C1000-207-SET1")
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS code TEXT;

-- Give existing rows a derived code if null
UPDATE exams SET code = 'EXAM-' || id::text WHERE code IS NULL;

-- Make code NOT NULL after backfill
ALTER TABLE exams
  ALTER COLUMN code SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_exams_code ON exams (code);

-- description
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS description TEXT;

-- duration_minutes: human-friendly alias; duration_secs already exists
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS duration_minutes INT
    GENERATED ALWAYS AS (duration_secs / 60) STORED;

-- pass_threshold: replaces passing_score (keep both; app uses pass_threshold)
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS pass_threshold NUMERIC(5,2) DEFAULT 68.0;

-- Backfill from passing_score if present
UPDATE exams SET pass_threshold = passing_score WHERE pass_threshold IS NULL AND passing_score IS NOT NULL;

-- max_attempts
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS max_attempts INT NOT NULL DEFAULT 5;

-- randomize_order
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS randomize_order BOOLEAN NOT NULL DEFAULT TRUE;

-- tags: JSONB array of topic tags
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]';

-- prerequisite_exam_id
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS prerequisite_exam_id UUID REFERENCES exams(id);

-- tenant_id (HC-4) — already added by 005 if that ran; safe to re-add
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS tenant_id UUID
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002';

-- draw_spec: per-domain question draw specification for rotating banks.
-- Already present in the base schema as NOT NULL; add here for databases
-- that were seeded from an older schema version that lacked this column.
-- NULL = draw all active questions for the set (backward-compatible).
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS draw_spec JSONB DEFAULT NULL;


-- ═══════════════════════════════════════════════════════════════
-- 2. quiz_attempts table
-- ═══════════════════════════════════════════════════════════════

-- pct_score: percentage score (0–100)
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS pct_score NUMERIC(5,2);

-- score: raw correct count (int)
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS score INT;

-- max_score: total question count at time of grading
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS max_score INT;

-- Note: raw_score column does not exist in live schema; backfill skipped.
-- focus_lost_count (already in base schema as focus_lost_count; safe to re-add)
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS focus_lost_count INT NOT NULL DEFAULT 0;

-- fullscreen_exits
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS fullscreen_exits INT NOT NULL DEFAULT 0;

-- clipboard_events
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS clipboard_events INT NOT NULL DEFAULT 0;

-- tab_switch_events
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS tab_switch_events JSONB NOT NULL DEFAULT '[]';

-- proctor_flags
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS proctor_flags JSONB NOT NULL DEFAULT '[]';

-- keystroke_entropy
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS keystroke_entropy NUMERIC(6,4);

-- cohort_id (already in base schema; safe)
ALTER TABLE quiz_attempts
  ADD COLUMN IF NOT EXISTS cohort_id TEXT;

-- grading_failed status support — add values to CHECK constraint
-- (PostgreSQL does not support ALTER CONSTRAINT; drop and recreate)
ALTER TABLE quiz_attempts DROP CONSTRAINT IF EXISTS quiz_attempts_status_check;
ALTER TABLE quiz_attempts
  ADD CONSTRAINT quiz_attempts_status_check
  CHECK (status IN (
    'in_progress','submitted','graded','flagged','voided',
    'grading','grading_failed'
  ));


-- ═══════════════════════════════════════════════════════════════
-- 3. questions table
-- ═══════════════════════════════════════════════════════════════

-- text: app queries SELECT text FROM questions; base schema uses "stem"
-- Add text as a generated/virtual alias first, then make it a real column
-- (PostgreSQL doesn't support generated columns from other text columns cleanly)
-- Strategy: add text column, backfill from stem, keep both in sync via trigger.
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS text TEXT;

UPDATE questions SET text = stem WHERE text IS NULL AND stem IS NOT NULL;

-- type: single-letter shorthand ('SC' | 'MR'); base schema uses question_type ('mcq' etc.)
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS type TEXT;

UPDATE questions
SET type = CASE
  WHEN question_type IN ('mcq','drag_order','short_answer') THEN 'SC'
  WHEN question_type = 'multi_select' THEN 'MR'
  ELSE 'SC'
END
WHERE type IS NULL;

-- correct_answers: TEXT[] of correct option labels (e.g. ['B'] or ['A','C'])
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS correct_answers TEXT[] NOT NULL DEFAULT '{}';

-- domain_number: numeric domain ordering
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS domain_number INT NOT NULL DEFAULT 1;

-- domain_name: human-readable domain label
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS domain_name TEXT NOT NULL DEFAULT 'General';

-- set_number: which practice set this question belongs to (1–6 for C1000-207)
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS set_number INT NOT NULL DEFAULT 1;

-- question_number: ordering within set
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS question_number INT NOT NULL DEFAULT 0;

-- ai_generated: already added by migration 003; safe to re-add
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS ai_generated BOOLEAN NOT NULL DEFAULT FALSE;

-- Trigger: keep text and stem in sync
CREATE OR REPLACE FUNCTION sync_question_text()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.text IS NOT NULL AND (NEW.stem IS NULL OR NEW.stem = '') THEN
    NEW.stem := NEW.text;
  ELSIF NEW.stem IS NOT NULL AND (NEW.text IS NULL OR NEW.text = '') THEN
    NEW.text := NEW.stem;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_question_text ON questions;
CREATE TRIGGER trg_sync_question_text
  BEFORE INSERT OR UPDATE ON questions
  FOR EACH ROW EXECUTE FUNCTION sync_question_text();


-- ═══════════════════════════════════════════════════════════════
-- 4. Indexes for new columns
-- ═══════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_questions_set_number     ON questions (set_number);
CREATE INDEX IF NOT EXISTS idx_questions_domain_number  ON questions (domain_number);
CREATE INDEX IF NOT EXISTS idx_questions_question_number ON questions (set_number, question_number);
CREATE INDEX IF NOT EXISTS idx_attempts_requires_review ON quiz_attempts (requires_review)
  WHERE requires_review = TRUE;

COMMIT;
