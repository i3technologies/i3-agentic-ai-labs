-- ============================================================
-- Consent Service — Database Migration 001
-- Creates consent_records and consent_audit tables.
-- HC-4: tenant_id UUID NOT NULL on all tables.
-- Apply: psql $CONSENT_DB_URL -f 001_init.sql
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── consent_records ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS consent_records (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID        NOT NULL,
    subject_id_hash  TEXT        NOT NULL,     -- HMAC-SHA256(subject_id, MEMBER_HMAC_SECRET)
    channel          TEXT        NOT NULL,     -- email | sms | push | whatsapp
    purpose          TEXT        NOT NULL,     -- marketing | transactional | analytics
    status           TEXT        NOT NULL CHECK (status IN ('granted','revoked','erased')),
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    source           TEXT,                     -- web-form | ussd | crm-import
    expiry           TIMESTAMPTZ,
    version          TEXT        NOT NULL DEFAULT '1.0',
    UNIQUE (tenant_id, subject_id_hash, channel, purpose)
);

CREATE INDEX IF NOT EXISTS idx_consent_tenant_subject
    ON consent_records (tenant_id, subject_id_hash);

-- RLS: each tenant only sees its own rows
ALTER TABLE consent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE consent_records FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON consent_records
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

CREATE POLICY superuser_bypass ON consent_records TO postgres USING (true);

-- ── consent_audit ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS consent_audit (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    consent_id  UUID        REFERENCES consent_records(id) ON DELETE SET NULL,
    tenant_id   UUID        NOT NULL,
    event_type  TEXT        NOT NULL,  -- granted | revoked | erased | checked
    actor       TEXT,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata    JSONB
);

CREATE INDEX IF NOT EXISTS idx_consent_audit_consent_id
    ON consent_audit (consent_id);
CREATE INDEX IF NOT EXISTS idx_consent_audit_tenant
    ON consent_audit (tenant_id, timestamp DESC);

ALTER TABLE consent_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE consent_audit FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON consent_audit
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

CREATE POLICY superuser_bypass ON consent_audit TO postgres USING (true);
