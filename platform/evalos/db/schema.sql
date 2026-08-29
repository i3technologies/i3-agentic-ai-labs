-- EvalOS Database Schema
-- Target: PostgreSQL 15 (Crunchy HA)
-- Database: evalos
-- Applied via Flyway / manual migration

BEGIN;

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- for fuzzy text search on questions

-- ── Question Bank ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS questions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic           TEXT NOT NULL,
    subtopic        TEXT,
    difficulty      SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    question_type   TEXT NOT NULL CHECK (question_type IN ('mcq', 'multi_select', 'code', 'short_answer', 'drag_order')),
    stem            TEXT NOT NULL,
    explanation     TEXT,
    -- MCQ options stored as JSONB: [{"id":"a","text":"..","is_correct":true}, ...]
    options         JSONB,
    -- Code questions: expected output / test harness
    test_harness    JSONB,
    tags            TEXT[] DEFAULT '{}',
    bloom_level     TEXT CHECK (bloom_level IN ('remember','understand','apply','analyze','evaluate','create')),
    source          TEXT,   -- curriculum reference
    moss_hash       TEXT,   -- normalized AST hash for plagiarism baseline
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_questions_topic        ON questions (topic);
CREATE INDEX idx_questions_difficulty   ON questions (difficulty);
CREATE INDEX idx_questions_type         ON questions (question_type);
CREATE INDEX idx_questions_tags         ON questions USING GIN (tags);
CREATE INDEX idx_questions_stem_trgm    ON questions USING GIN (stem gin_trgm_ops);

-- ── Exam Definitions ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exams (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           TEXT NOT NULL,
    description     TEXT,
    -- Draw spec: [{"topic":"..","count":5,"difficulty_min":2,"difficulty_max":4}, ...]
    draw_spec       JSONB NOT NULL,
    duration_secs   INT NOT NULL DEFAULT 3600,
    passing_score   NUMERIC(5,2) NOT NULL DEFAULT 70.0,
    profile         CHAR(1) CHECK (profile IN ('A','B','C','D')),
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    created_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Quiz Attempts ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exam_id             UUID NOT NULL REFERENCES exams(id),
    student_id          TEXT NOT NULL,   -- Keycloak subject
    cohort_id           TEXT,
    -- Randomized question order + shuffled options snapshot
    question_snapshot   JSONB NOT NULL,
    answers             JSONB NOT NULL DEFAULT '{}',
    -- Anti-cheat telemetry
    focus_lost_count    INT NOT NULL DEFAULT 0,
    clipboard_events    INT NOT NULL DEFAULT 0,
    fullscreen_exits    INT NOT NULL DEFAULT 0,
    tab_switch_events   JSONB NOT NULL DEFAULT '[]',
    keystroke_entropy   NUMERIC(6,4),   -- anomaly detection
    proctor_flags       JSONB NOT NULL DEFAULT '[]',
    -- Timing
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at        TIMESTAMPTZ,
    graded_at           TIMESTAMPTZ,
    -- Scores
    raw_score           NUMERIC(5,2),
    percentage          NUMERIC(5,2),
    passed              BOOLEAN,
    -- MOSS plagiarism
    moss_similarity     NUMERIC(5,2),   -- 0–100%
    moss_report_url     TEXT,
    status              TEXT NOT NULL DEFAULT 'in_progress'
                        CHECK (status IN ('in_progress','submitted','graded','flagged','voided')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_attempts_student   ON quiz_attempts (student_id);
CREATE INDEX idx_attempts_exam      ON quiz_attempts (exam_id);
CREATE INDEX idx_attempts_status    ON quiz_attempts (status);
CREATE INDEX idx_attempts_cohort    ON quiz_attempts (cohort_id);

-- ── Per-Question Attempt Detail ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attempt_answers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id      UUID NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id     UUID NOT NULL REFERENCES questions(id),
    answer_value    JSONB,          -- student's selected option(s) or code
    is_correct      BOOLEAN,
    partial_score   NUMERIC(5,2),
    time_spent_secs INT,
    submission_id   UUID            -- FK to sandbox daemon result (code questions)
);

CREATE INDEX idx_answers_attempt ON attempt_answers (attempt_id);

-- ── User Weaknesses (adaptive learning map) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS user_weaknesses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      TEXT NOT NULL,
    topic           TEXT NOT NULL,
    subtopic        TEXT,
    -- Exponential moving average of performance (0–1)
    ema_score       NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    attempts        INT NOT NULL DEFAULT 0,
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, topic, subtopic)
);

CREATE INDEX idx_weaknesses_student ON user_weaknesses (student_id);
CREATE INDEX idx_weaknesses_topic   ON user_weaknesses (topic);

-- ── Sandbox Execution Results ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sandbox_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id   UUID NOT NULL UNIQUE,
    attempt_id      UUID REFERENCES quiz_attempts(id),
    student_id      TEXT NOT NULL,
    profile         CHAR(1),
    status          TEXT,
    stdout          TEXT,
    stderr          TEXT,
    exit_code       INT,
    wall_time_ms    NUMERIC(10,2),
    boot_time_ms    NUMERIC(10,2),
    cpu_time_ms     NUMERIC(10,2),
    memory_peak_kb  INT,
    test_results    JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Triggers: updated_at ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_questions_updated
    BEFORE UPDATE ON questions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Adaptive weakness updater function ───────────────────────────────────────
CREATE OR REPLACE FUNCTION update_weakness(
    p_student_id TEXT,
    p_topic TEXT,
    p_subtopic TEXT,
    p_correct BOOLEAN
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_score NUMERIC := CASE WHEN p_correct THEN 1.0 ELSE 0.0 END;
    v_alpha NUMERIC := 0.2;  -- EMA decay factor
BEGIN
    INSERT INTO user_weaknesses (student_id, topic, subtopic, ema_score, attempts, last_seen_at)
    VALUES (p_student_id, p_topic, p_subtopic, v_score, 1, NOW())
    ON CONFLICT (student_id, topic, subtopic) DO UPDATE
        SET ema_score   = (v_alpha * v_score) + ((1 - v_alpha) * user_weaknesses.ema_score),
            attempts    = user_weaknesses.attempts + 1,
            last_seen_at = NOW();
END;
$$;

COMMIT;
