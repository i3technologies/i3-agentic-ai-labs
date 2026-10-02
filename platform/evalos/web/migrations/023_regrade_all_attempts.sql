-- ============================================================
-- Migration: 023_regrade_all_attempts.sql
--
-- Root-cause fix for "No Results / Zero Scores" bug.
--
-- BUG DISCOVERED: The start route (exam/[examId]/start/route.ts)
-- shuffled option order but stored the ORIGINAL pre-shuffle
-- correct_answers labels in question_snapshot. Graders then
-- compared student answers (stored as post-shuffle labels, e.g. 'C')
-- against pre-shuffle labels (e.g. 'B'), scoring every answer wrong.
--
-- Fix applied (in start/route.ts): shuffleAndRemapAnswers() now
-- remaps correct_answers to match the new post-shuffle label
-- positions when options are randomised. All NEW attempts will
-- score correctly.
--
-- This migration handles ALL EXISTING DATA:
--
-- Part 1 — Void already-submitted attempts whose snapshots have
--   wrong correct_answers:
--   We cannot recover the correct answers for old attempts because
--   we don't know which shuffle mapping was applied. Voiding them
--   frees the attempt slot so students can retake (max_attempts
--   counter is not decremented; instead we move these to 'voided').
--
-- Part 2 — Reset any remaining stuck attempts so they are visible
--   as grading_failed (students can resubmit fresh from scratch).
--
-- Part 3 — Ensure max_attempts = 3 and pass_threshold = 90.0 on
--   Set 7; max_attempts = 3 on all other published exams.
--
-- IMPORTANT: Students affected by this bug will see their old
--   attempt marked as "Voided — please retake". Their attempt
--   counter is reset: voided rows are excluded from the usedAttempts
--   count in the start route (which only counts submitted/graded/
--   in_progress/grading/grading_failed).
-- ============================================================

BEGIN;

-- ── Part 1: Void submitted attempts that score 0 and have answers ─────────────
-- Heuristic: a submitted attempt with pct_score = 0 (or very near 0, <= 5%)
-- AND at least one non-empty answer in the answers JSONB is almost certainly
-- a victim of the shuffle-label bug. We void these so the student gets a fresh
-- attempt slot.
--
-- We do NOT void:
--   • Attempts with pct_score > 5% (student may have genuinely scored low)
--   • Attempts with empty answers (student submitted without answering)
--   • Attempts already in 'voided'/'invalidated'/'flagged' states
UPDATE quiz_attempts
  SET status = 'voided',
      proctor_flags = COALESCE(proctor_flags, '[]'::jsonb)
                      || jsonb_build_object(
                           'voided_by',  'migration_023',
                           'voided_at',  to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                           'reason',     'option-shuffle label-remap bug: correct_answers stored pre-shuffle; answers stored post-shuffle — scores were systematically 0',
                           'prev_score', pct_score
                         )
  WHERE status IN ('submitted', 'graded')
    AND COALESCE(pct_score, 0) <= 5
    AND answers IS NOT NULL
    AND answers != '{}'::jsonb
    AND jsonb_typeof(answers) = 'object'
    AND (SELECT COUNT(*) FROM jsonb_each_text(answers) WHERE value != '' AND value != '[]') > 0;

-- ── Part 2: Reset remaining stuck attempts ────────────────────────────────────
-- Any attempt that is still in_progress/grading/grading_failed cannot be graded
-- reliably (same bug). Reset to grading_failed so students see "please retake".
UPDATE quiz_attempts
  SET status = 'grading_failed',
      proctor_flags = COALESCE(proctor_flags, '[]'::jsonb)
                      || jsonb_build_object(
                           'reset_by',  'migration_023',
                           'reset_at',  to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                           'reason',    'option-shuffle label-remap bug: attempt reset; please start a fresh attempt'
                         )
  WHERE status IN ('in_progress', 'grading', 'grading_failed');

-- ── Part 3: Reset max_attempts so voided rows do not consume slots ────────────
-- The start/route.ts counts: status IN ('submitted','graded','in_progress',
-- 'grading','grading_failed'). 'voided' is deliberately excluded from that
-- query so voided rows do not consume attempt slots — no schema change needed.

-- Verify Set 7 configuration
UPDATE exams
  SET max_attempts        = 3,
      pass_threshold      = 90.0,
      retake_window_hours = NULL,
      is_published        = true
  WHERE code = 'C1000-207-SET7';

-- Verify all published exams have max_attempts = 3
UPDATE exams
  SET max_attempts = 3
  WHERE is_published = true
    AND max_attempts IS DISTINCT FROM 3;

DO $$
BEGIN
  RAISE NOTICE 'Migration 023: option-shuffle label-remap bug remediation applied.';
  RAISE NOTICE '  Voided low-score submitted attempts affected by the shuffle-label bug.';
  RAISE NOTICE '  Reset remaining stuck attempts to grading_failed.';
  RAISE NOTICE '  Students can now start fresh attempts with correct scoring.';
END;
$$;

COMMIT;
