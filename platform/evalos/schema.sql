-- ============================================================
-- EvalOS Database Schema
-- Database: evalos_db (PostgreSQL 15)
-- Created by: Crunchy PostgreSQL operator (i3-data namespace)
-- ============================================================

-- ── Extensions ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Questions Bank ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS questions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stem            TEXT NOT NULL,
    question_type   VARCHAR(20) NOT NULL CHECK (question_type IN ('mcq', 'coding', 'essay', 'iac')),
    options         JSONB,                  -- MCQ: [{text, is_correct}]
    test_harness    JSONB,                  -- Coding: [{input, expected_output}]
    solution        TEXT,                  -- Instructor-only reference answer
    topic           VARCHAR(100) NOT NULL,
    subtopic        VARCHAR(100),
    difficulty      INTEGER NOT NULL CHECK (difficulty BETWEEN 1 AND 10),
    bloom_level     VARCHAR(20) CHECK (bloom_level IN ('remember','understand','apply','analyze','evaluate','create')),
    profile         CHAR(1) CHECK (profile IN ('A','B','C','D')),  -- EvalOS execution profile
    points          INTEGER NOT NULL DEFAULT 10,
    time_limit_secs INTEGER,
    tags            TEXT[],
    author_id       UUID,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_questions_topic ON questions (topic);
CREATE INDEX idx_questions_difficulty ON questions (difficulty);
CREATE INDEX idx_questions_active ON questions (is_active) WHERE is_active = TRUE;

-- ── Exams ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exams (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    cohort_id       VARCHAR(50),
    track           CHAR(1) CHECK (track IN ('A','B','C','D')),
    duration_secs   INTEGER NOT NULL DEFAULT 5400,  -- 90 minutes default
    draw_spec       JSONB NOT NULL,                 -- [{topic, count, difficulty_min, difficulty_max}]
    pass_threshold  NUMERIC(5,2) NOT NULL DEFAULT 60.0,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    start_time      TIMESTAMPTZ,
    end_time        TIMESTAMPTZ,
    created_by      UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_exams_cohort ON exams (cohort_id);
CREATE INDEX idx_exams_published ON exams (is_published) WHERE is_published = TRUE;

-- ── Quiz Attempts ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exam_id             UUID NOT NULL REFERENCES exams(id),
    student_id          VARCHAR(255) NOT NULL,  -- Keycloak subject claim
    cohort_id           VARCHAR(50),
    status              VARCHAR(20) NOT NULL DEFAULT 'in_progress'
                            CHECK (status IN ('in_progress','submitted','graded','flagged','invalidated')),
    question_snapshot   JSONB NOT NULL,         -- Randomized question order + shuffled options
    answers             JSONB DEFAULT '{}',     -- {question_id: answer_value}
    score               NUMERIC(5,2),
    max_score           NUMERIC(5,2),
    pct_score           NUMERIC(5,2),
    passed              BOOLEAN,
    -- Anti-cheat counters
    focus_lost_count    INTEGER NOT NULL DEFAULT 0,
    fullscreen_exits    INTEGER NOT NULL DEFAULT 0,
    clipboard_events    INTEGER NOT NULL DEFAULT 0,
    tab_switch_events   JSONB NOT NULL DEFAULT '[]',
    proctor_flags       JSONB NOT NULL DEFAULT '[]',
    -- Timing
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at        TIMESTAMPTZ,
    graded_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_attempts_student ON quiz_attempts (student_id);
CREATE INDEX idx_attempts_exam ON quiz_attempts (exam_id);
CREATE INDEX idx_attempts_status ON quiz_attempts (status);
CREATE INDEX idx_attempts_cohort ON quiz_attempts (cohort_id);

-- ── Code Submissions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS code_submissions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id      UUID REFERENCES quiz_attempts(id),
    question_id     UUID REFERENCES questions(id),
    student_id      VARCHAR(255) NOT NULL,
    profile         CHAR(1) NOT NULL CHECK (profile IN ('A','B','C','D')),
    code            TEXT NOT NULL,
    language        VARCHAR(30) NOT NULL DEFAULT 'python',
    status          VARCHAR(20) NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','running','passed','failed','timeout','error')),
    stdout          TEXT,
    stderr          TEXT,
    exit_code       INTEGER,
    boot_ms         NUMERIC(10,2),
    exec_ms         NUMERIC(10,2),
    test_results    JSONB,
    score           NUMERIC(5,2),
    plagiarism_score NUMERIC(5,2),
    moss_report_url TEXT,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_submissions_attempt ON code_submissions (attempt_id);
CREATE INDEX idx_submissions_student ON code_submissions (student_id);
CREATE INDEX idx_submissions_status ON code_submissions (status);

-- ── AI Interview Rounds ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_interviews (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      VARCHAR(255) NOT NULL,
    cohort_id       VARCHAR(50),
    model           VARCHAR(100) NOT NULL DEFAULT 'granite-nano',
    transcript      JSONB NOT NULL DEFAULT '[]',  -- [{role, content, ts}]
    evaluation      JSONB,                        -- {scores, summary, recommendation}
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','in_progress','completed','error')),
    final_score     NUMERIC(5,2),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_interviews_student ON ai_interviews (student_id);

-- ── Instructor Question Sets ──────────────────────────────────
CREATE TABLE IF NOT EXISTS question_sets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    question_ids    UUID[] NOT NULL,
    author_id       UUID NOT NULL,
    is_public       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Enrolment Queue (auto-enrolment trigger) ──────────────────
CREATE TABLE IF NOT EXISTS enrolment_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    cohort_id       VARCHAR(50) NOT NULL,
    evalos_score    NUMERIC(5,2) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','provisioning','provisioned','failed')),
    ai_lab_ns       VARCHAR(100),
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provisioned_at  TIMESTAMPTZ
);

CREATE INDEX idx_enrolment_status ON enrolment_queue (status);

-- ── Updated_at trigger ────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER questions_updated_at BEFORE UPDATE ON questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER exams_updated_at BEFORE UPDATE ON exams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
