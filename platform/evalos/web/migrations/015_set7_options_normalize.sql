-- ============================================================
-- Migration: 015_set7_options_normalize.sql
-- Normalize Set 7 question options from plain strings to
-- {label, text} objects matching the schema used by Sets 1–6.
--
-- Problem: Set 7 questions were seeded with options stored as
-- a JSON array of plain strings:
--   ["Option text A", "Option text B", "Option text C", "Option text D"]
--
-- The exam client (exam-client.tsx) expects each option to be an
-- object with shape {label: string, text: string}. When it renders
-- opt.text on a plain string, the value is undefined, so the exam
-- displays empty boxes with no text in the answer choices.
--
-- Fix: convert to {label, text} objects (A, B, C, D).
-- This matches the format of all other question sets in the DB.
--
-- Applied live via psql on 2026-09-25. Safe to re-run
-- (the WHERE clause limits updates to rows still in string format).
-- ============================================================

BEGIN;

UPDATE questions
SET options = (
  SELECT jsonb_agg(
    jsonb_build_object(
      'label', chr(64 + rn::int),
      'text',  val
    )
    ORDER BY rn
  )
  FROM (
    SELECT
      row_number() OVER () AS rn,
      val
    FROM jsonb_array_elements_text(questions.options) AS val
  ) sub
)
WHERE set_number = 7
  AND jsonb_typeof(options->0) = 'string';

COMMIT;

-- Verification:
-- SELECT COUNT(*) FROM questions
--  WHERE set_number = 7
--    AND jsonb_typeof(options->0) = 'string';
-- Expected: 0 (all converted)
--
-- SELECT question_number, options->0 FROM questions
--  WHERE set_number = 7 ORDER BY question_number LIMIT 3;
-- Expected: {"label": "A", "text": "..."} objects
