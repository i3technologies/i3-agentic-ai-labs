-- i3-Engage Database Schema
-- Apply: psql engage_db < migrations/001_init.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Contact Lists ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contact_lists (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  description TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Contacts ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contacts (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       TEXT NOT NULL UNIQUE,
  first_name  TEXT DEFAULT '',
  last_name   TEXT DEFAULT '',
  company     TEXT DEFAULT '',
  phone       TEXT,
  subscribed  BOOLEAN DEFAULT TRUE,
  tags        TEXT[] DEFAULT '{}',
  list_ids    UUID[] DEFAULT '{}',
  custom_data JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_contacts_email     ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_subscribed ON contacts(subscribed);

-- ── Contact Events (opens, clicks, bounces) ───────────────────
CREATE TABLE IF NOT EXISTS contact_events (
  id          BIGSERIAL PRIMARY KEY,
  contact_id  TEXT NOT NULL,    -- email or UUID reference
  event_type  TEXT NOT NULL,    -- delivered | opened | clicked | bounced | unsubscribed
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_contact  ON contact_events(contact_id);
CREATE INDEX IF NOT EXISTS idx_events_type     ON contact_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created  ON contact_events(created_at DESC);

-- ── Email Campaigns ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_campaigns (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name           TEXT NOT NULL,
  subject        TEXT NOT NULL,
  html_template  TEXT NOT NULL,
  from_name      TEXT DEFAULT 'i3 Engage',
  from_email     TEXT DEFAULT 'hello@i3technologies.co.ke',
  list_id        UUID REFERENCES contact_lists(id),
  status         TEXT DEFAULT 'draft' CHECK (status IN ('draft','scheduled','sent','paused')),
  ai_personalise BOOLEAN DEFAULT FALSE,
  scheduled_at   TIMESTAMPTZ,
  sent_at        TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Email Sends (per-contact send record) ─────────────────────
CREATE TABLE IF NOT EXISTS email_sends (
  id          BIGSERIAL PRIMARY KEY,
  campaign_id UUID REFERENCES email_campaigns(id),
  contact_id  UUID REFERENCES contacts(id),
  batch_id    UUID,
  status      TEXT DEFAULT 'pending',
  error       TEXT,
  sent_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sends_campaign ON email_sends(campaign_id);
CREATE INDEX IF NOT EXISTS idx_sends_contact  ON email_sends(contact_id);

-- ── SMS Messages ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sms_messages (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id          UUID REFERENCES contacts(id),
  provider            TEXT DEFAULT 'africastalking',
  provider_message_id TEXT UNIQUE,
  content             TEXT NOT NULL,
  status              TEXT DEFAULT 'pending',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ
);
