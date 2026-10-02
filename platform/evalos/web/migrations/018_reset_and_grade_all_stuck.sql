-- ============================================================
-- Migration: 018_reset_and_grade_all_stuck.sql
--
-- Problem: Students see "in_progress", "grading", or
--          "grading_failed" attempts stuck permanently —
--          no score, no result page.
--
-- Solution:
--   Grade ALL stuck attempts immediately using pure SQL / PL/pgSQL
--   arithmetic that mirrors the TypeScript gradeInline logic in
--   platform/evalos/web/src/app/api/exam/[examId]/submit/route.ts.
--   Works even when the external grading-service pod is down.
--
-- Scope (no time-gate — rescues everything regardless of age):
--   • status = 'in_progress'    (student never submitted)
--   • status = 'grading'        (submitted, pod died mid-grade)
--   • status = 'grading_failed' (previously rescued, still ungraded)
--
-- Already-submitted / graded attempts are NOT touched.
--
-- Scoring logic (mirrors gradeInline exactly):
--   SC  – student answer UPPER() = correct_answers[0] UPPER()
--   MR  – sorted student labels array = sorted correct_answers array
--   No answer / empty → incorrect
--
-- Integrity scores:
--   trust_score=100 / requires_review=false for all rescued attempts
--   (no telemetry available for orphaned sessions).
--
-- Safe to re-run (idempotent):
--   The WHERE clause limits updates to stuck statuses only.
--   Rows already in 'submitted'/'graded' are untouched.
-- ============================================================

BEGIN;

-- ── PL/pgSQL block: grade every stuck attempt in a cursor loop ────────────────
DO $$
DECLARE
  rec            RECORD;
  q              RECORD;
  total_qs       INT;
  correct_qs     INT;
  pct            NUMERIC(7,4);
  pass_thr       NUMERIC(5,2);
  is_passed      BOOLEAN;
  student_ans    TEXT;
  student_arr    TEXT[];
  correct_arr    TEXT[];
  rescued        INT := 0;
BEGIN

  -- Iterate over every stuck attempt
  FOR rec IN
    SELECT
      qa.id,
      qa.question_snapshot,
      qa.answers,
      qa.status,
      COALESCE(e.pass_threshold, e.passing_score, 68)::NUMERIC(5,2) AS pass_threshold
    FROM quiz_attempts qa
    JOIN exams e ON e.id = qa.exam_id
    WHERE qa.status IN ('in_progress', 'grading', 'grading_failed')
  LOOP
    total_qs   := 0;
    correct_qs := 0;

    -- Iterate each question in the snapshot
    FOR q IN
      SELECT
        val->>'id'           AS q_id,
        UPPER(COALESCE(val->>'type', 'SC')) AS q_type,
        val->'correct_answers' AS correct_answers_json
      FROM jsonb_array_elements(rec.question_snapshot) AS val
    LOOP
      total_qs := total_qs + 1;

      -- Extract correct_answers as a TEXT array
      SELECT ARRAY(
        SELECT UPPER(elem #>> '{}')
        FROM jsonb_array_elements(q.correct_answers_json) AS elem
      ) INTO correct_arr;

      IF q.q_type = 'MR' THEN
        -- ── Multiple Response: sorted arrays must match exactly ──────────
        IF rec.answers ? q.q_id
           AND jsonb_typeof(rec.answers->q.q_id) = 'array'
        THEN
          SELECT ARRAY(
            SELECT UPPER(elem #>> '{}')
            FROM jsonb_array_elements(rec.answers->q.q_id) AS elem
            ORDER BY 1
          ) INTO student_arr;

          -- Sort correct answers too
          correct_arr := ARRAY(
            SELECT unnest(correct_arr) ORDER BY 1
          );

          IF student_arr = correct_arr THEN
            correct_qs := correct_qs + 1;
          END IF;
        END IF;

      ELSE
        -- ── Single Choice: student answer matches first correct answer ───
        IF rec.answers ? q.q_id THEN
          student_ans := UPPER(
            COALESCE(
              -- string answer
              CASE WHEN jsonb_typeof(rec.answers->q.q_id) = 'string'
                   THEN rec.answers->>(q.q_id)
                   ELSE NULL END,
              ''
            )
          );

          IF student_ans = correct_arr[1] THEN
            correct_qs := correct_qs + 1;
          END IF;
        END IF;
      END IF;

    END LOOP; -- end per-question loop

    -- Compute percentage score and pass/fail
    IF total_qs > 0 THEN
      pct       := ROUND((correct_qs::NUMERIC / total_qs) * 100, 4);
      is_passed := pct >= rec.pass_threshold;
    ELSE
      pct       := 0;
      is_passed := FALSE;
    END IF;

    pass_thr := rec.pass_threshold;

    -- Persist the grade result
    UPDATE quiz_attempts
    SET
      status               = 'submitted',
      submitted_at         = COALESCE(submitted_at, NOW()),
      score                = correct_qs,
      max_score            = total_qs,
      pct_score            = pct,
      passed               = is_passed,
      -- Neutral integrity scores — no telemetry for orphaned sessions
      identity_score       = 100,
      behavior_score       = 100,
      integrity_confidence = 100,
      trust_score          = 100,
      requires_review      = FALSE,
      -- Audit trail
      proctor_flags        = COALESCE(proctor_flags, '[]'::jsonb)
                             || jsonb_build_object(
                                  'graded_by',    'migration_018',
                                  'prev_status',  rec.status,
                                  'graded_at',    to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                                  'score',        correct_qs,
                                  'max_score',    total_qs,
                                  'pct_score',    pct,
                                  'note',         'inline SQL grader — grading service was unavailable'
                                )
    WHERE id = rec.id;

    rescued := rescued + 1;
  END LOOP; -- end per-attempt loop

  RAISE NOTICE 'Migration 018: % attempt(s) rescued and graded.', rescued;
END;
$$;

COMMIT;
