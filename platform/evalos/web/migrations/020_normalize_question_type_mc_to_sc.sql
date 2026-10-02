-- ============================================================
-- Migration: 020_normalize_question_type_mc_to_sc.sql
--
-- Problem: Set 7 questions seeded in migration 012 used
-- type = 'MC' (multiple choice, single answer). The application
-- and grading service treat anything that is NOT 'MR' as a
-- single-choice question, so 'MC' functions correctly but is
-- inconsistent with Sets 1–6 which use 'SC'.
--
-- Fix: rename 'MC' → 'SC' across the questions table so all
-- single-choice questions use the same type code.
--
-- Safe to re-run (WHERE clause limits to 'MC' only).
-- ============================================================

BEGIN;

UPDATE questions
  SET type = 'SC'
  WHERE type = 'MC';

-- Verify: SELECT DISTINCT type FROM questions WHERE set_number = 7;
-- Expected: 'SC' and 'MR' only.

COMMIT;
