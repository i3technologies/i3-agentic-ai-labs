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
    -- HC-4: tenant isolation (NULL = shared/system question visible to all tenants)
    tenant_id       UUID,
    topic           TEXT NOT NULL DEFAULT 'General',
    subtopic        TEXT,
    difficulty      TEXT NOT NULL DEFAULT 'intermediate',
    question_type   TEXT NOT NULL DEFAULT 'mcq',
    -- stem = canonical field; text = application alias (kept in sync by trigger)
    stem            TEXT NOT NULL DEFAULT '',
    text            TEXT,   -- alias for stem; synced by trg_sync_question_text trigger
    -- type = 'SC' | 'MR' shorthand; synced from question_type
    type            TEXT,
    explanation     TEXT,
    -- MCQ options stored as JSONB array of {label, text} objects
    options         JSONB,
    -- correct_answers: TEXT[] of correct option labels (e.g. ['B'] or ['A','C'])
    correct_answers TEXT[] NOT NULL DEFAULT '{}',
    -- Domain organisation (C1000-207 uses domain_number 1–7)
    domain_number   INT NOT NULL DEFAULT 1,
    domain_name     TEXT NOT NULL DEFAULT 'General',
    -- Set organisation (1–7 for C1000-207 practice sets)
    set_number      INT NOT NULL DEFAULT 1,
    question_number INT NOT NULL DEFAULT 0,
    -- Code questions: expected output / test harness
    test_harness    JSONB,
    tags            TEXT[] DEFAULT '{}',
    bloom_level     TEXT,
    source          TEXT,   -- curriculum reference
    moss_hash       TEXT,   -- normalized AST hash for plagiarism baseline
    ai_generated    BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_questions_topic        ON questions (topic);
CREATE INDEX idx_questions_type         ON questions (question_type);
CREATE INDEX idx_questions_set_number   ON questions (set_number);
CREATE INDEX idx_questions_domain       ON questions (domain_number);
CREATE INDEX idx_questions_set_q        ON questions (set_number, question_number);
CREATE INDEX idx_questions_tags         ON questions USING GIN (tags);
CREATE INDEX idx_questions_stem_trgm    ON questions USING GIN (stem gin_trgm_ops);

-- ── Exam Definitions ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exams (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title                TEXT NOT NULL,
    description          TEXT,
    -- Exam code displayed in UI (e.g. "C1000-207-SET1")
    code                 VARCHAR(50),
    -- tags: JSONB array of topic tags
    tags                 JSONB NOT NULL DEFAULT '[]',
    -- HC-4: tenant isolation
    tenant_id            UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
    -- Draw spec: [{"topic":"..","count":5,"difficulty_min":2,"difficulty_max":4}, ...]
    -- NULL = draw all active questions for the set (backward-compatible)
    draw_spec            JSONB DEFAULT NULL,
    duration_secs        INT NOT NULL DEFAULT 5400,
    -- Derived convenience column used by dashboard query (duration_secs / 60)
    duration_minutes     INTEGER GENERATED ALWAYS AS (duration_secs / 60) STORED,
    -- pass_threshold is the authoritative column (NOT generated); passing_score is
    -- a backward-compat alias used in some older queries.
    pass_threshold       NUMERIC(5,2) NOT NULL DEFAULT 68.0,
    passing_score        NUMERIC(5,2) GENERATED ALWAYS AS (pass_threshold) STORED,
    -- Maximum attempts a student may make (1 initial + 2 retakes = 3 total)
    max_attempts         INTEGER NOT NULL DEFAULT 3,
    -- set_number parsed from code (e.g. "SET1" → 1) for question_count subquery
    set_number           INTEGER GENERATED ALWAYS AS (
                             CASE WHEN code ~ 'SET[0-9]+$'
                             THEN REGEXP_REPLACE(code, '^.*SET', '')::integer
                             ELSE 0 END
                         ) STORED,
    -- Prerequisite: student must pass this exam before attempting this one
    prerequisite_exam_id UUID REFERENCES exams(id),
    -- Deprecated: no retake window enforced. Students may retake at any time within max_attempts.
    retake_window_hours  INTEGER,
    -- Whether to shuffle question order per attempt
    randomize_order      BOOLEAN NOT NULL DEFAULT TRUE,
    profile              CHAR(1) CHECK (profile IN ('A','B','C','D')),
    is_published         BOOLEAN NOT NULL DEFAULT FALSE,
    created_by           TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Quiz Attempts ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exam_id             UUID NOT NULL REFERENCES exams(id),
    student_id          TEXT NOT NULL,   -- Keycloak subject
    -- HC-4: tenant isolation
    tenant_id           UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
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
    device_fingerprint  TEXT,
    -- Timing
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at        TIMESTAMPTZ,
    graded_at           TIMESTAMPTZ,
    -- Scores (written directly by the submit route; NOT generated columns)
    score               INT,
    max_score           INT,
    pct_score           NUMERIC(7,4),
    passed              BOOLEAN,
    -- Integrity scores (written by submit route)
    identity_score      NUMERIC(5,2),
    behavior_score      NUMERIC(5,2),
    integrity_confidence NUMERIC(5,2),
    trust_score         NUMERIC(5,2),
    requires_review     BOOLEAN NOT NULL DEFAULT FALSE,
    -- MOSS plagiarism
    moss_similarity     NUMERIC(5,2),   -- 0–100%
    moss_report_url     TEXT,
    status              TEXT NOT NULL DEFAULT 'in_progress'
                        CHECK (status IN ('in_progress','grading','grading_failed','submitted','graded','flagged','voided')),
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
