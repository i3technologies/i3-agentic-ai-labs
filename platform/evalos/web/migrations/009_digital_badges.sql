-- ============================================================
-- Migration: 009_digital_badges.sql
-- EvalOS Phase 2: Open Badges 3.0 / Verifiable Credentials tables.
--
-- Implements badge class definitions and per-candidate credential
-- issuance records with revocation support.
--
-- Source: §5 Layer 6, §2.1 of ARCH-EVALOS-2026-V2
-- HC-4: tenant_id UUID NOT NULL on all tables.
-- ============================================================

BEGIN;

-- ── Badge Class Definitions ───────────────────────────────────────────────────
-- Each row is an Open Badges 3.0 BadgeClass (the template).
-- A badge class is tied to a specific exam / skill competency.
CREATE TABLE IF NOT EXISTS badge_classes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  slug             VARCHAR(64) NOT NULL,
  name             VARCHAR(255) NOT NULL,
  description      TEXT NOT NULL,
  criteria_url     VARCHAR(512),    -- URL to human-readable criteria page
  image_url        VARCHAR(512),    -- Badge image (SVG or PNG)
  issuer_name      VARCHAR(255) NOT NULL DEFAULT 'i3 Technologies Limited',
  issuer_url       VARCHAR(512) NOT NULL DEFAULT 'https://i3technologies.co.ke',
  issuer_email     VARCHAR(255) NOT NULL DEFAULT 'credentials@i3technologies.co.ke',
  alignment        JSONB NOT NULL DEFAULT '[]',   -- skill framework alignments
  tags             TEXT[] NOT NULL DEFAULT '{}',
  -- Requirement: minimum score to earn this badge
  min_score        NUMERIC(5,2) NOT NULL DEFAULT 70.0,
  -- Linked to an exam or assessment blueprint
  exam_id          UUID REFERENCES exams(id) ON DELETE SET NULL,
  blueprint_id     UUID REFERENCES assessment_blueprints(id) ON DELETE SET NULL,
  ob3_context      JSONB NOT NULL DEFAULT '["https://www.w3.org/2018/credentials/v1","https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json"]',
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_badge_classes_tenant ON badge_classes (tenant_id);
CREATE INDEX IF NOT EXISTS idx_badge_classes_exam   ON badge_classes (exam_id);

ALTER TABLE badge_classes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS badge_classes_tenant_isolation ON badge_classes;
CREATE POLICY badge_classes_tenant_isolation ON badge_classes
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Credential Issuances ──────────────────────────────────────────────────────
-- Each row is an issued Open Badge 3.0 OpenBadgeCredential.
-- Includes revocation support per OB3 spec.
CREATE TABLE IF NOT EXISTS credential_issuances (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  badge_class_id       UUID NOT NULL REFERENCES badge_classes(id),
  candidate_id         VARCHAR(128) NOT NULL,
  candidate_email      VARCHAR(255) NOT NULL,
  candidate_name       VARCHAR(255),
  attempt_id           UUID REFERENCES quiz_attempts(id) ON DELETE SET NULL,
  session_id           UUID REFERENCES assessment_sessions(id) ON DELETE SET NULL,
  -- Scores at time of issuance
  score_pct            NUMERIC(5,2) NOT NULL,
  performance_band     VARCHAR(32),
  skill_vector         JSONB NOT NULL DEFAULT '{}',
  -- OB3 credential fields
  credential_id        VARCHAR(255) UNIQUE NOT NULL,  -- URL or URN used as @id
  issued_on            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_on           TIMESTAMPTZ,
  -- Revocation
  is_revoked           BOOLEAN NOT NULL DEFAULT FALSE,
  revoked_at           TIMESTAMPTZ,
  revocation_reason    TEXT,
  -- Verification
  verification_code    VARCHAR(64) UNIQUE NOT NULL,   -- short code for QR/URL verify
  certificate_hash     VARCHAR(128),                   -- SHA-256 of the PDF cert
  -- Full OB3 credential JSON cached for serving
  ob3_credential       JSONB NOT NULL DEFAULT '{}',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credentials_tenant      ON credential_issuances (tenant_id);
CREATE INDEX IF NOT EXISTS idx_credentials_candidate   ON credential_issuances (candidate_id);
CREATE INDEX IF NOT EXISTS idx_credentials_badge_class ON credential_issuances (badge_class_id);
CREATE INDEX IF NOT EXISTS idx_credentials_verify_code ON credential_issuances (verification_code);
CREATE INDEX IF NOT EXISTS idx_credentials_revoked     ON credential_issuances (is_revoked) WHERE is_revoked = FALSE;

ALTER TABLE credential_issuances ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS credential_issuances_tenant_isolation ON credential_issuances;
CREATE POLICY credential_issuances_tenant_isolation ON credential_issuances
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Certification Readiness Scores ────────────────────────────────────────────
-- Tracks per-candidate certification-readiness band over multiple attempts.
CREATE TABLE IF NOT EXISTS cert_readiness_scores (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  candidate_id     VARCHAR(128) NOT NULL,
  exam_id          UUID REFERENCES exams(id),
  attempt_id       UUID REFERENCES quiz_attempts(id),
  readiness_band   VARCHAR(32) NOT NULL
    CHECK (readiness_band IN ('READY','ALMOST_READY','NEEDS_PREPARATION','NOT_READY')),
  predicted_pass_prob  NUMERIC(5,4),   -- 0.0–1.0 predicted pass probability
  weak_domains     JSONB NOT NULL DEFAULT '[]',
  next_actions     JSONB NOT NULL DEFAULT '[]',
  computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cert_readiness_tenant    ON cert_readiness_scores (tenant_id);
CREATE INDEX IF NOT EXISTS idx_cert_readiness_candidate ON cert_readiness_scores (candidate_id);
CREATE INDEX IF NOT EXISTS idx_cert_readiness_exam      ON cert_readiness_scores (exam_id);

ALTER TABLE cert_readiness_scores ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cert_readiness_tenant_isolation ON cert_readiness_scores;
CREATE POLICY cert_readiness_tenant_isolation ON cert_readiness_scores
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Seed: default badge class for C1000-207 watsonx Orchestrate exam ─────────
INSERT INTO badge_classes (
  tenant_id, slug, name, description, issuer_name, min_score, tags
) VALUES (
  '00000000-0000-0000-0000-000000000002',
  'wxo-ai-engineer-associate',
  'IBM watsonx Orchestrate AI Engineer Associate',
  'Awarded to candidates who demonstrate proficiency in designing, building, and deploying AI-powered workflows using IBM watsonx Orchestrate.',
  'i3 Technologies Limited',
  70.0,
  ARRAY['ibm','watsonx','ai-engineer','associate']
) ON CONFLICT (tenant_id, slug) DO NOTHING;

-- ── updated_at trigger for badge_classes ──────────────────────────────────────
DROP TRIGGER IF EXISTS trg_badge_classes_updated ON badge_classes;
CREATE TRIGGER trg_badge_classes_updated
  BEFORE UPDATE ON badge_classes
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
