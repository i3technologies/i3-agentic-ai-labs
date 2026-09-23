-- ============================================================
-- Migration: 010_platform_marketplace.sql
-- EvalOS Phase 3: Skills Passport, Workforce Intelligence,
--   Assessment Marketplace, and Public Skills API tables.
--
-- Source: §10 Phase 3 of ARCH-EVALOS-2026-V2
-- HC-4: tenant_id UUID NOT NULL on all tables.
-- ============================================================

BEGIN;

-- ── Skills Passport ───────────────────────────────────────────────────────────
-- One record per candidate — the portable professional identity.
CREATE TABLE IF NOT EXISTS skills_passports (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  candidate_id      VARCHAR(128) NOT NULL UNIQUE,
  candidate_email   VARCHAR(255) NOT NULL,
  candidate_name    VARCHAR(255),
  -- Aggregated multi-dimensional proficiency snapshot (denormalized for fast serving)
  skill_summary     JSONB NOT NULL DEFAULT '{}',
  -- Employability mapping: array of matching roles/programmes
  employability     JSONB NOT NULL DEFAULT '[]',
  -- Total credentials issued
  credential_count  INT NOT NULL DEFAULT 0,
  -- Overall tier: BEGINNER / INTERMEDIATE / ADVANCED / EXPERT
  tier              VARCHAR(32) NOT NULL DEFAULT 'BEGINNER'
    CHECK (tier IN ('BEGINNER','INTERMEDIATE','ADVANCED','EXPERT')),
  is_public         BOOLEAN NOT NULL DEFAULT FALSE,  -- opt-in for employer search
  public_token      VARCHAR(64) UNIQUE,               -- random URL token for share link
  last_updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_passports_tenant    ON skills_passports (tenant_id);
CREATE INDEX IF NOT EXISTS idx_passports_candidate ON skills_passports (candidate_id);
CREATE INDEX IF NOT EXISTS idx_passports_public    ON skills_passports (is_public, tier) WHERE is_public = TRUE;

ALTER TABLE skills_passports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS skills_passports_tenant_isolation ON skills_passports;
CREATE POLICY skills_passports_tenant_isolation ON skills_passports
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Workforce Organisation Skills Inventory ───────────────────────────────────
-- Each row represents a skill held by an employee within an organisation.
CREATE TABLE IF NOT EXISTS org_skills (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  org_id          UUID NOT NULL,         -- organisation UUID (from Keycloak realm or custom)
  employee_id     VARCHAR(128) NOT NULL,
  skill_id        UUID REFERENCES skill_nodes(id) ON DELETE CASCADE,
  proficiency     NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (proficiency BETWEEN 0 AND 100),
  source          VARCHAR(32) NOT NULL DEFAULT 'assessed'
    CHECK (source IN ('assessed','self_reported','certified','inferred')),
  evidence_ref    UUID,
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, org_id, employee_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_org_skills_tenant ON org_skills (tenant_id);
CREATE INDEX IF NOT EXISTS idx_org_skills_org    ON org_skills (org_id);
CREATE INDEX IF NOT EXISTS idx_org_skills_emp    ON org_skills (employee_id);
CREATE INDEX IF NOT EXISTS idx_org_skills_skill  ON org_skills (skill_id);

ALTER TABLE org_skills ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_skills_tenant_isolation ON org_skills;
CREATE POLICY org_skills_tenant_isolation ON org_skills
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Assessment Marketplace Listings ──────────────────────────────────────────
-- Third-party authors publish assessments; i3 takes a 20–30% revenue share.
CREATE TABLE IF NOT EXISTS marketplace_listings (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  author_id        VARCHAR(128) NOT NULL,
  title            VARCHAR(255) NOT NULL,
  description      TEXT NOT NULL,
  price_usd        NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (price_usd >= 0),
  currency         VARCHAR(8) NOT NULL DEFAULT 'USD',
  -- Revenue share
  platform_share   NUMERIC(5,2) NOT NULL DEFAULT 25.0 CHECK (platform_share BETWEEN 0 AND 100),
  -- Linked to an exam or blueprint
  exam_id          UUID REFERENCES exams(id) ON DELETE SET NULL,
  blueprint_id     UUID REFERENCES assessment_blueprints(id) ON DELETE SET NULL,
  -- Categorisation
  skill_tags       TEXT[] NOT NULL DEFAULT '{}',
  target_roles     TEXT[] NOT NULL DEFAULT '{}',
  difficulty_level VARCHAR(32) CHECK (difficulty_level IN ('BEGINNER','INTERMEDIATE','ADVANCED','EXPERT')),
  -- Status
  status           VARCHAR(32) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','pending_review','published','suspended','withdrawn')),
  review_notes     TEXT,
  -- Metrics
  sales_count      INT NOT NULL DEFAULT 0,
  avg_rating       NUMERIC(3,2),
  review_count     INT NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_marketplace_tenant ON marketplace_listings (tenant_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_author ON marketplace_listings (author_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_status ON marketplace_listings (status);
CREATE INDEX IF NOT EXISTS idx_marketplace_tags   ON marketplace_listings USING GIN (skill_tags);

ALTER TABLE marketplace_listings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS marketplace_listings_tenant_isolation ON marketplace_listings;
CREATE POLICY marketplace_listings_tenant_isolation ON marketplace_listings
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Marketplace Purchases ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS marketplace_purchases (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  listing_id       UUID NOT NULL REFERENCES marketplace_listings(id),
  buyer_id         VARCHAR(128) NOT NULL,
  amount_paid_usd  NUMERIC(8,2) NOT NULL,
  platform_fee_usd NUMERIC(8,2) NOT NULL,
  author_payout    NUMERIC(8,2) NOT NULL,
  payment_ref      TEXT,
  purchased_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_purchases_tenant  ON marketplace_purchases (tenant_id);
CREATE INDEX IF NOT EXISTS idx_purchases_listing ON marketplace_purchases (listing_id);
CREATE INDEX IF NOT EXISTS idx_purchases_buyer   ON marketplace_purchases (buyer_id);

ALTER TABLE marketplace_purchases ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS marketplace_purchases_tenant_isolation ON marketplace_purchases;
CREATE POLICY marketplace_purchases_tenant_isolation ON marketplace_purchases
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── AI Engineering Assessment Sessions ───────────────────────────────────────
-- Tracks sessions for the AI Engineering assessment mode (§6.4 AI-native tier).
-- Modes: closed_book / ai_allowed / ai_engineering
CREATE TABLE IF NOT EXISTS ai_engineering_sessions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000002',
  attempt_id        UUID REFERENCES quiz_attempts(id),
  candidate_id      VARCHAR(128) NOT NULL,
  mode              VARCHAR(32) NOT NULL DEFAULT 'ai_allowed'
    CHECK (mode IN ('closed_book','ai_allowed','ai_engineering')),
  -- Metrics captured during the session
  prompts_sent      INT NOT NULL DEFAULT 0,
  prompt_quality    NUMERIC(5,2),    -- scored by AI-Collaboration agent
  hallucinations_caught INT NOT NULL DEFAULT 0,
  output_verified   BOOLEAN,
  -- Agent scores
  ai_collab_score   NUMERIC(5,2),
  final_score       NUMERIC(5,2),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_eng_sessions_tenant    ON ai_engineering_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_eng_sessions_candidate ON ai_engineering_sessions (candidate_id);

ALTER TABLE ai_engineering_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_engineering_sessions_tenant_isolation ON ai_engineering_sessions;
CREATE POLICY ai_engineering_sessions_tenant_isolation ON ai_engineering_sessions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── updated_at trigger for marketplace listings ───────────────────────────────
DROP TRIGGER IF EXISTS trg_marketplace_updated ON marketplace_listings;
CREATE TRIGGER trg_marketplace_updated
  BEFORE UPDATE ON marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
