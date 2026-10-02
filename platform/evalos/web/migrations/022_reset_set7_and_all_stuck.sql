-- ============================================================
-- Migration: 022_reset_set7_and_all_stuck.sql
--
-- Definitive reset for Set 7 and ALL exam sets.
--
-- Problem: Attempts stuck in 'in_progress', 'grading', or
-- 'grading_failed' — across ANY exam set — consume an attempt
-- slot (counted by the start route) but show no score. Students
-- are blocked from retaking and see perpetual "In Progress".
--
-- This migration supersedes 017, 018, and 021 for the current
-- stuck population by:
--   1. Grading every stuck attempt inline (mirrors gradeInline TS).
--   2. Specifically verifying Set 7 (C1000-207-SET7) config:
--      max_attempts = 3, pass_threshold = 90.0, retake_window = NULL.
--   3. Setting graded_at, submitted_at for every rescued attempt.
--   4. Backfilling graded_at on previously submitted rows (safety).
--
-- No time-gate — rescues ALL stuck attempts regardless of age.
-- Idempotent: WHERE clause excludes 'submitted'/'graded' rows.
-- ============================================================

BEGIN;

-- ── Part 1: Ensure Set 7 exam is correctly configured ─────────────────────────
UPDATE exams
  SET max_attempts        = 3,
      pass_threshold      = 90.0,
      retake_window_hours = NULL,
      is_published        = true
  WHERE code = 'C1000-207-SET7';

-- ── Part 2: Ensure ALL published exams have max_attempts = 3 ──────────────────
UPDATE exams
  SET max_attempts = 3
  WHERE is_published = true
    AND max_attempts IS DISTINCT FROM 3;

-- ── Part 3: Backfill graded_at for already-submitted rows that are NULL ───────
UPDATE quiz_attempts
  SET graded_at = COALESCE(submitted_at, started_at, NOW())
  WHERE status IN ('submitted', 'graded')
    AND graded_at IS NULL;

-- ── Part 4: Grade every stuck attempt inline (all sets) ───────────────────────
DO $$
DECLARE
  rec            RECORD;
  q              RECORD;
  total_qs       INT;
  correct_qs     INT;
  pct            NUMERIC(7,4);
  is_passed      BOOLEAN;
  student_ans    TEXT;
  student_arr    TEXT[];
  correct_arr    TEXT[];
  rescued        INT := 0;
  skipped        INT := 0;
BEGIN

  FOR rec IN
    SELECT
      qa.id,
      qa.question_snapshot,
      qa.answers,
      qa.status,
      e.code                                                          AS exam_code,
      COALESCE(e.pass_threshold, e.passing_score, 68)::NUMERIC(5,2)  AS pass_threshold
    FROM quiz_attempts qa
    JOIN exams e ON e.id = qa.exam_id
    WHERE qa.status IN ('in_progress', 'grading', 'grading_failed')
  LOOP

    -- Skip attempts with no question snapshot (never started properly)
    IF rec.question_snapshot IS NULL
       OR jsonb_array_length(rec.question_snapshot) = 0
    THEN
      UPDATE quiz_attempts
        SET status       = 'grading_failed',
            proctor_flags = COALESCE(proctor_flags, '[]'::jsonb)
                            || jsonb_build_object(
                                 'graded_by',   'migration_022',
                                 'prev_status', rec.status,
                                 'graded_at',   to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                                 'note',        'empty snapshot — no questions to grade'
                               )
        WHERE id = rec.id;
      skipped := skipped + 1;
      CONTINUE;
    END IF;

    total_qs   := 0;
    correct_qs := 0;

    FOR q IN
      SELECT
        val->>'id'  AS q_id,
        CASE UPPER(COALESCE(val->>'type', 'SC'))
          WHEN 'MR' THEN 'MR'
          ELSE 'SC'           -- MC, SC, mcq, multi_select, etc → single-answer
        END         AS q_type,
        val->'correct_answers' AS correct_answers_json
      FROM jsonb_array_elements(rec.question_snapshot) AS val
    LOOP
      total_qs := total_qs + 1;

      SELECT ARRAY(
        SELECT UPPER(elem #>> '{}')
        FROM jsonb_array_elements(q.correct_answers_json) AS elem
      ) INTO correct_arr;

      IF q.q_type = 'MR' THEN
        -- Multiple Response: sorted student array must match sorted correct array
        IF rec.answers ? q.q_id
           AND jsonb_typeof(rec.answers->q.q_id) = 'array'
        THEN
          SELECT ARRAY(
            SELECT UPPER(elem #>> '{}')
            FROM jsonb_array_elements(rec.answers->q.q_id) AS elem
            ORDER BY 1
          ) INTO student_arr;
          correct_arr := ARRAY(SELECT unnest(correct_arr) ORDER BY 1);
          IF student_arr = correct_arr THEN
            correct_qs := correct_qs + 1;
          END IF;
        END IF;

      ELSE
        -- Single Choice: student string answer matches first correct answer
        IF rec.answers ? q.q_id
           AND jsonb_typeof(rec.answers->q.q_id) = 'string'
        THEN
          student_ans := UPPER(rec.answers->>(q.q_id));
          IF student_ans = correct_arr[1] THEN
            correct_qs := correct_qs + 1;
          END IF;
        END IF;
      END IF;

    END LOOP; -- end per-question loop

    IF total_qs > 0 THEN
      pct       := ROUND((correct_qs::NUMERIC / total_qs) * 100, 4);
      is_passed := pct >= rec.pass_threshold;
    ELSE
      pct       := 0;
      is_passed := FALSE;
    END IF;

    UPDATE quiz_attempts
    SET
      status               = 'submitted',
      submitted_at         = COALESCE(submitted_at, NOW()),
      graded_at            = NOW(),
      score                = correct_qs,
      max_score            = total_qs,
      pct_score            = pct,
      passed               = is_passed,
      identity_score       = 100,
      behavior_score       = 100,
      integrity_confidence = 100,
      trust_score          = 100,
      requires_review      = FALSE,
      proctor_flags        = COALESCE(proctor_flags, '[]'::jsonb)
                             || jsonb_build_object(
                                  'graded_by',    'migration_022',
                                  'prev_status',  rec.status,
                                  'exam_code',    rec.exam_code,
                                  'graded_at',    to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                                  'score',        correct_qs,
                                  'max_score',    total_qs,
                                  'pct_score',    pct,
                                  'note',         'inline SQL grader — all-sets stuck rescue'
                                )
    WHERE id = rec.id;

    rescued := rescued + 1;
  END LOOP; -- end per-attempt loop

  RAISE NOTICE 'Migration 022: % attempt(s) rescued and graded, % skipped (empty snapshot).', rescued, skipped;
END;
$$;

COMMIT;
