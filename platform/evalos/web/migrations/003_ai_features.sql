-- ============================================================
-- Migration: 003_ai_features.sql
-- Adds columns + tables needed for Phase 2 AI features:
--   - questions.ai_generated       (flag for AI-generated drafts)
--   - questions.updated_at         (timestamp for last edit)
--   - ai_interview_evaluations     (AI Interview round scores)
--   - ai_interview_questions       (optional: DB-driven interview questions)
-- Safe to run multiple times (uses IF NOT EXISTS / ALTER ... IF NOT EXISTS)
-- ============================================================

-- ── questions table extensions ─────────────────────────────────
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS ai_generated BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- Backfill updated_at for existing rows
UPDATE questions SET updated_at = NOW() WHERE updated_at IS NULL;

-- ── ai_interview_evaluations ───────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_interview_evaluations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_id         TEXT NOT NULL,
  question_id     TEXT NOT NULL,
  student_id      TEXT NOT NULL,
  question_type   TEXT NOT NULL CHECK (question_type IN ('text','code')),
  student_answer  TEXT NOT NULL,
  score           INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
  feedback        TEXT NOT NULL DEFAULT '',
  strengths       JSONB NOT NULL DEFAULT '[]',
  improvements    JSONB NOT NULL DEFAULT '[]',
  model_used      TEXT NOT NULL DEFAULT '',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ,

  -- One evaluation per (exam, question, student) — upserted on retake
  UNIQUE (exam_id, question_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_aie_student ON ai_interview_evaluations (student_id);
CREATE INDEX IF NOT EXISTS idx_aie_exam    ON ai_interview_evaluations (exam_id);

-- ── ai_interview_questions ─────────────────────────────────────
-- Optional: if you want DB-driven interview questions instead of
-- the static set in /app/interview/page.tsx
CREATE TABLE IF NOT EXISTS ai_interview_questions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  text        TEXT NOT NULL,
  type        TEXT NOT NULL CHECK (type IN ('text','code')),
  language    TEXT,             -- 'javascript' | 'python' | 'sql'
  rubric      TEXT NOT NULL,
  time_limit  INTEGER NOT NULL DEFAULT 420,  -- seconds
  sort_order  INTEGER NOT NULL DEFAULT 0,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_interview_questions IS
  'Optional DB-driven question set for /interview. Falls back to static set if empty.';
