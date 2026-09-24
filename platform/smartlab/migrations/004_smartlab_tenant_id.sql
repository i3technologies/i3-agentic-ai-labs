-- ============================================================
-- Migration: 004_smartlab_tenant_id.sql
-- HC-4 Remediation: adds tenant_id UUID NOT NULL to all SmartLab
-- tables and enables Row-Level Security.
--
-- Default tenant: 00000000-0000-0000-0000-000000000001
--   (i3 production tenant — update per-row once real tenant
--    mapping is known)
--
-- Safe to run multiple times (uses IF NOT EXISTS).
-- Apply: psql $SMARTLAB_DB_URL < migrations/004_smartlab_tenant_id.sql
-- ============================================================

BEGIN;

-- ── 1. authors ────────────────────────────────────────────────────────────────
ALTER TABLE authors ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_authors_tenant ON authors (tenant_id);
ALTER TABLE authors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON authors;
CREATE POLICY tenant_isolation ON authors
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 2. courses ────────────────────────────────────────────────────────────────
ALTER TABLE courses ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_courses_tenant ON courses (tenant_id);
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON courses;
CREATE POLICY tenant_isolation ON courses
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 3. modules ────────────────────────────────────────────────────────────────
ALTER TABLE modules ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_modules_tenant ON modules (tenant_id);
ALTER TABLE modules ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON modules;
CREATE POLICY tenant_isolation ON modules
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 4. lessons ────────────────────────────────────────────────────────────────
ALTER TABLE lessons ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_lessons_tenant ON lessons (tenant_id);
ALTER TABLE lessons ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON lessons;
CREATE POLICY tenant_isolation ON lessons
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 5. quizzes ────────────────────────────────────────────────────────────────
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_quizzes_tenant ON quizzes (tenant_id);
ALTER TABLE quizzes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON quizzes;
CREATE POLICY tenant_isolation ON quizzes
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 6. quiz_questions ─────────────────────────────────────────────────────────
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_quiz_questions_tenant ON quiz_questions (tenant_id);
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON quiz_questions;
CREATE POLICY tenant_isolation ON quiz_questions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 7. books ──────────────────────────────────────────────────────────────────
ALTER TABLE books ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_books_tenant ON books (tenant_id);
ALTER TABLE books ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON books;
CREATE POLICY tenant_isolation ON books
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 8. book_chapters ──────────────────────────────────────────────────────────
ALTER TABLE book_chapters ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_book_chapters_tenant ON book_chapters (tenant_id);
ALTER TABLE book_chapters ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON book_chapters;
CREATE POLICY tenant_isolation ON book_chapters
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 9. live_sessions ──────────────────────────────────────────────────────────
ALTER TABLE live_sessions ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_live_sessions_tenant ON live_sessions (tenant_id);
ALTER TABLE live_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON live_sessions;
CREATE POLICY tenant_isolation ON live_sessions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 10. ai_jobs ───────────────────────────────────────────────────────────────
ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_ai_jobs_tenant ON ai_jobs (tenant_id);
ALTER TABLE ai_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON ai_jobs;
CREATE POLICY tenant_isolation ON ai_jobs
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 11. xapi_statements ───────────────────────────────────────────────────────
ALTER TABLE xapi_statements ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_xapi_statements_tenant ON xapi_statements (tenant_id);
ALTER TABLE xapi_statements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON xapi_statements;
CREATE POLICY tenant_isolation ON xapi_statements
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── 12. content_library ───────────────────────────────────────────────────────
ALTER TABLE content_library ADD COLUMN IF NOT EXISTS tenant_id UUID
  NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';
CREATE INDEX IF NOT EXISTS idx_content_library_tenant ON content_library (tenant_id);
ALTER TABLE content_library ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON content_library;
CREATE POLICY tenant_isolation ON content_library
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

COMMIT;

-- ── Post-migration checklist ──────────────────────────────────────────────────
-- 1. Backfill actual tenant UUIDs if multiple SmartLab tenants exist:
--    UPDATE courses SET tenant_id = '<real-uuid>' WHERE ...;
-- 2. Update SmartLab application routes to call:
--    SET LOCAL app.tenant_id = '<uuid>' before any table query.
-- 3. Prefix all S3 object keys with {tenant_id}/ to prevent cross-tenant
--    object storage access (courses.s3_scorm_key, lessons.narration_s3_key, etc.).
