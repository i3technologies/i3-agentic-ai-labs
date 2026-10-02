-- ============================================================
-- Migration: 021_grade_all_stuck_attempts.sql
--
-- Definitive rescue migration.
-- Grades EVERY stuck attempt immediately, regardless of age:
--   • status = 'in_progress'    — timed out without submission
--   • status = 'grading'        — pod died mid-grade
--   • status = 'grading_failed' — previously rescued, still ungraded
--
-- Also backfills graded_at on already-submitted rows that are NULL.
--
-- This is the authoritative version superseding migrations 017 and 018:
--   • No time-gate (unlike 017 which required >5 min / >24 h)
--   • Handles 'MC' type correctly (same as 'SC' — single answer)
--   • Sets graded_at = NOW() on every rescued row
--   • Idempotent: WHERE clause excludes 'submitted'/'graded' rows
-- ============================================================

BEGIN;

-- ── Part 1: Backfill graded_at for already-submitted rows ────────────────────
UPDATE quiz_attempts
  SET graded_at = COALESCE(submitted_at, started_at, NOW())
  WHERE status IN ('submitted', 'graded')
    AND graded_at IS NULL;

-- ── Part 2: Grade every stuck attempt inline ─────────────────────────────────
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

    FOR q IN
      SELECT
        val->>'id'             AS q_id,
        -- MC and SC are both single-answer; MR requires all correct labels
        CASE UPPER(COALESCE(val->>'type', 'SC'))
          WHEN 'MR' THEN 'MR'
          ELSE 'SC'
        END                    AS q_type,
        val->'correct_answers' AS correct_answers_json
      FROM jsonb_array_elements(rec.question_snapshot) AS val
    LOOP
      total_qs := total_qs + 1;

      SELECT ARRAY(
        SELECT UPPER(elem #>> '{}')
        FROM jsonb_array_elements(q.correct_answers_json) AS elem
      ) INTO correct_arr;

      IF q.q_type = 'MR' THEN
        -- Multiple Response: sorted student array must exactly match sorted correct array
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

    END LOOP;

    IF total_qs > 0 THEN
      pct       := ROUND((correct_qs::NUMERIC / total_qs) * 100, 4);
      is_passed := pct >= rec.pass_threshold;
    ELSE
      pct       := 0;
      is_passed := FALSE;
    END IF;

    pass_thr := rec.pass_threshold;

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
                                  'graded_by',    'migration_021',
                                  'prev_status',  rec.status,
                                  'graded_at',    to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                                  'score',        correct_qs,
                                  'max_score',    total_qs,
                                  'pct_score',    pct,
                                  'note',         'inline SQL grader — all-stuck rescue'
                                )
    WHERE id = rec.id;

    rescued := rescued + 1;
  END LOOP;

  RAISE NOTICE 'Migration 021: % attempt(s) rescued and graded.', rescued;
END;
$$;

COMMIT;
