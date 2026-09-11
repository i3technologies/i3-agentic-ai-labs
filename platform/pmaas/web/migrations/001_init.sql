-- PMaaS Database Schema
-- Apply: psql pmaas_db < migrations/001_init.sql

-- ── Extensions ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Wards ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wards (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  county      TEXT NOT NULL DEFAULT 'Machakos',
  constituency TEXT,
  population  INTEGER,
  registered_voters INTEGER,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wards_county ON wards(county);

-- ── Campaigns ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaigns (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  description TEXT,
  status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','paused','completed')),
  start_date  DATE,
  end_date    DATE,
  budget_kes  NUMERIC(15,2) DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ
);

-- ── Ward Targets ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ward_targets (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  ward_id         UUID NOT NULL REFERENCES wards(id),
  priority        INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
  registered_voters INTEGER,
  target_votes    INTEGER,
  sentiment_score NUMERIC(5,2),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (campaign_id, ward_id)
);

CREATE INDEX IF NOT EXISTS idx_ward_targets_campaign ON ward_targets(campaign_id);

-- ── Voters ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS voters (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  phone         TEXT UNIQUE,
  ward_id       UUID REFERENCES wards(id),
  voter_status  TEXT DEFAULT 'registered',
  contacted     BOOLEAN DEFAULT FALSE,
  support_level TEXT DEFAULT 'unknown' CHECK (support_level IN ('strong','lean','unknown','against')),
  notes         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voters_ward ON voters(ward_id);
CREATE INDEX IF NOT EXISTS idx_voters_support ON voters(support_level);

-- ── Volunteers ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS volunteers (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  phone      TEXT UNIQUE,
  ward_id    UUID REFERENCES wards(id),
  status     TEXT DEFAULT 'active' CHECK (status IN ('active','inactive')),
  role       TEXT DEFAULT 'field_agent',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Campaign Activity log ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaign_activity (
  id          BIGSERIAL PRIMARY KEY,
  type        TEXT NOT NULL,
  description TEXT NOT NULL,
  metadata    JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_created ON campaign_activity(created_at DESC);

-- ── AI Briefings archive ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_briefings (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     TEXT,
  briefing    JSONB NOT NULL,
  model_used  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── WhatsApp / Voice interactions ─────────────────────────────
CREATE TABLE IF NOT EXISTS voter_interactions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  voter_id      UUID REFERENCES voters(id),
  channel       TEXT NOT NULL CHECK (channel IN ('whatsapp','voice','sms','in_person')),
  direction     TEXT DEFAULT 'outbound' CHECK (direction IN ('inbound','outbound')),
  content       TEXT,
  sentiment     TEXT,
  campaign_id   UUID REFERENCES campaigns(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interactions_voter ON voter_interactions(voter_id);
CREATE INDEX IF NOT EXISTS idx_interactions_campaign ON voter_interactions(campaign_id);
