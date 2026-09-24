-- ============================================================
-- i3 SmartLab — PostgreSQL Schema
-- Run inside Crunchy PG primary pod:
--   oc exec i3-postgres-primary-hffm-0 -n i3-data -c database \
--     -- psql -U postgres -f /tmp/smartlab-schema.sql
-- ============================================================

-- Create database + user
SELECT 'CREATE DATABASE smartlab_db' WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'smartlab_db'
)\gexec

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'smartlab') THEN
    -- HC-7: password must be injected from OpenBao at deploy time.
    -- Run: CREATE USER smartlab WITH PASSWORD :'SMARTLAB_DB_PASSWORD';
    -- where SMARTLAB_DB_PASSWORD is sourced from: vault kv get i3/smartlab/db
    RAISE EXCEPTION 'smartlab role does not exist — create it with a password from OpenBao (i3/smartlab/db)';
  END IF;
END$$;

GRANT ALL PRIVILEGES ON DATABASE smartlab_db TO smartlab;

-- Connect to smartlab_db for schema creation
\connect smartlab_db

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- full-text search on titles

-- -------------------------------------------------------
-- AUTHORS
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS authors (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  keycloak_id   TEXT UNIQUE NOT NULL,
  email         TEXT UNIQUE NOT NULL,
  full_name     TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'author'
                CHECK (role IN ('admin','author','reviewer','publisher')),
  avatar_url    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_authors_keycloak ON authors(keycloak_id);

-- -------------------------------------------------------
-- COURSES
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  author_id        UUID NOT NULL REFERENCES authors(id) ON DELETE SET NULL,
  title            TEXT NOT NULL,
  description      TEXT,
  topic            TEXT,
  level            TEXT DEFAULT 'beginner'
                   CHECK (level IN ('beginner','intermediate','advanced','expert')),
  language         TEXT DEFAULT 'en',
  duration_minutes INTEGER,
  status           TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft','review','published','archived')),
  scorm_version    TEXT DEFAULT '2004'
                   CHECK (scorm_version IN ('1.2','2004')),
  moodle_course_id INTEGER,          -- populated after Moodle publish
  moodle_module_id INTEGER,          -- SCORM activity ID in Moodle
  s3_scorm_key     TEXT,             -- seaweedfs S3 object key for SCORM ZIP
  thumbnail_url    TEXT,
  tags             TEXT[],
  blooms_profile   JSONB,            -- {"remember":30,"understand":20,...}
  ai_generated     BOOLEAN DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_author   ON courses(author_id);
CREATE INDEX IF NOT EXISTS idx_courses_status   ON courses(status);
CREATE INDEX IF NOT EXISTS idx_courses_title_trgm ON courses USING GIN (title gin_trgm_ops);

-- -------------------------------------------------------
-- MODULES (chapters within a course)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS modules (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id     UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  description   TEXT,
  position      INTEGER NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_modules_course ON modules(course_id);

-- -------------------------------------------------------
-- LESSONS (SCOs within a module)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS lessons (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  module_id        UUID NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  course_id        UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,
  content_html     TEXT,               -- rich HTML body (Tiptap output)
  narration_s3_key TEXT,               -- TTS audio for this lesson
  slide_data       JSONB,              -- [{slide:1, title:"...", body:"...", notes:"..."}]
  video_s3_key     TEXT,               -- if lesson has a video
  hls_url          TEXT,               -- served HLS URL
  transcript       TEXT,               -- STT transcript
  vtt_s3_key       TEXT,               -- subtitle VTT file
  duration_seconds INTEGER,
  position         INTEGER NOT NULL DEFAULT 0,
  ai_generated     BOOLEAN DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lessons_module ON lessons(module_id);
CREATE INDEX IF NOT EXISTS idx_lessons_course ON lessons(course_id);

-- -------------------------------------------------------
-- QUIZZES
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS quizzes (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lesson_id    UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
  title        TEXT NOT NULL DEFAULT 'Knowledge Check',
  passing_score INTEGER DEFAULT 80,
  max_attempts  INTEGER DEFAULT 3,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------
-- QUIZ QUESTIONS
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_questions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  quiz_id         UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
  question_text   TEXT NOT NULL,
  question_type   TEXT NOT NULL DEFAULT 'mcq'
                  CHECK (question_type IN ('mcq','true_false','short_answer','fill_blank')),
  options         JSONB,      -- [{"id":"a","text":"...","correct":true},...]
  explanation     TEXT,       -- shown after answer
  blooms_level    TEXT CHECK (blooms_level IN ('remember','understand','apply','analyse','evaluate','create')),
  position        INTEGER NOT NULL DEFAULT 0,
  ai_generated    BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questions_quiz ON quiz_questions(quiz_id);

-- -------------------------------------------------------
-- DIGITAL BOOKS (EPUB3)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS books (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  author_id      UUID NOT NULL REFERENCES authors(id),
  title          TEXT NOT NULL,
  subtitle       TEXT,
  description    TEXT,
  language       TEXT DEFAULT 'en',
  status         TEXT NOT NULL DEFAULT 'draft'
                 CHECK (status IN ('draft','review','published','archived')),
  source_s3_key  TEXT,         -- original uploaded document
  epub_s3_key    TEXT,         -- built EPUB3 file
  moodle_file_id INTEGER,      -- Moodle resource ID after publish
  cover_s3_key   TEXT,
  isbn           TEXT,
  publisher      TEXT DEFAULT 'i3 Technologies',
  tags           TEXT[],
  ai_generated   BOOLEAN DEFAULT FALSE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------
-- BOOK CHAPTERS
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS book_chapters (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  book_id          UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,
  content_html     TEXT,
  narration_s3_key TEXT,          -- TTS audio per chapter
  image_s3_key     TEXT,          -- chapter illustration
  position         INTEGER NOT NULL DEFAULT 0,
  word_count       INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chapters_book ON book_chapters(book_id);

-- -------------------------------------------------------
-- LIVE STREAM SESSIONS
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS live_sessions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id       UUID REFERENCES courses(id),
  author_id       UUID NOT NULL REFERENCES authors(id),
  title           TEXT NOT NULL,
  stream_key      TEXT UNIQUE NOT NULL,
  rtmp_url        TEXT,
  hls_url         TEXT,
  status          TEXT NOT NULL DEFAULT 'scheduled'
                  CHECK (status IN ('scheduled','live','ended','vod_ready')),
  scheduled_at    TIMESTAMPTZ,
  started_at      TIMESTAMPTZ,
  ended_at        TIMESTAMPTZ,
  viewer_count    INTEGER DEFAULT 0,
  vod_lesson_id   UUID REFERENCES lessons(id),  -- created after stream ends
  chat_enabled    BOOLEAN DEFAULT TRUE,
  ai_tutor_enabled BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_live_sessions_course  ON live_sessions(course_id);
CREATE INDEX IF NOT EXISTS idx_live_sessions_key     ON live_sessions(stream_key);

-- -------------------------------------------------------
-- AI GENERATION JOBS (async task tracking)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_jobs (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  job_type     TEXT NOT NULL
               CHECK (job_type IN (
                 'course_outline','lesson_content','quiz_gen',
                 'narration','transcription','video_chapters',
                 'epub_build','scorm_package','subtitle_gen'
               )),
  entity_type  TEXT,         -- 'course','lesson','book','chapter','live_session'
  entity_id    UUID,
  status       TEXT NOT NULL DEFAULT 'queued'
               CHECK (status IN ('queued','running','done','failed')),
  progress     INTEGER DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  model_used   TEXT,
  prompt_tokens  INTEGER,
  result_tokens  INTEGER,
  error_message  TEXT,
  result_data    JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_jobs_entity  ON ai_jobs(entity_id);
CREATE INDEX IF NOT EXISTS idx_ai_jobs_status  ON ai_jobs(status);

-- -------------------------------------------------------
-- XAPI STATEMENTS (local buffer before Langfuse sync)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS xapi_statements (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  actor_email     TEXT NOT NULL,
  verb            TEXT NOT NULL,
  object_id       TEXT NOT NULL,
  object_type     TEXT,
  result_score    NUMERIC(5,2),
  result_success  BOOLEAN,
  result_duration TEXT,
  context_course  UUID,
  raw_statement   JSONB NOT NULL,
  synced_langfuse BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_xapi_actor  ON xapi_statements(actor_email);
CREATE INDEX IF NOT EXISTS idx_xapi_synced ON xapi_statements(synced_langfuse) WHERE synced_langfuse = FALSE;

-- -------------------------------------------------------
-- CONTENT LIBRARY (semantic search cache)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS content_library (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  entity_type   TEXT NOT NULL,   -- 'lesson','quiz_question','chapter'
  entity_id     UUID NOT NULL,
  title         TEXT,
  content_text  TEXT,
  embed_vector  TEXT,             -- stored as JSON array string (ChromaDB is primary)
  chroma_id     TEXT,             -- ChromaDB document ID
  tags          TEXT[],
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------
-- TRIGGER: updated_at auto-update
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['authors','courses','lessons','books','ai_jobs']
  LOOP
    EXECUTE format('
      DROP TRIGGER IF EXISTS trg_updated_%1$s ON %1$s;
      CREATE TRIGGER trg_updated_%1$s
        BEFORE UPDATE ON %1$s
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    ', tbl);
  END LOOP;
END$$;

-- Grant all to smartlab user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO smartlab;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO smartlab;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO smartlab;

-- Confirm
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
