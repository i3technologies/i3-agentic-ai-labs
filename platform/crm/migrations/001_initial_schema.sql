-- ============================================================
-- Migration: 001_initial_schema.sql
-- Database:  crm_db  (Crunchy PostgreSQL, namespace i3-crm)
--
-- Creates the four core CRM Intelligence tables with:
--   • HC-4: tenant_id UUID NOT NULL on every table
--   • HC-4: Row-Level Security (RLS) on every table using the
--           NULLIF pattern from platform/evalos/web/migrations/014_fix_rls_empty_tenant.sql
--   • HC-6: email_hash / phone_hash columns accept only the
--           output of keyed HMAC-SHA256 (enforced at app layer).
--           Raw SHA-256 is NOT accepted (see crawl engine).
--   • Immutable evidence ledger: UPDATE/DELETE blocked by RLS
--           policy — append-only by design.
--
-- Naming conventions follow i3 platform standards:
--   • Indexes: idx_<table>_<column(s)>
--   • Policies: <table>_tenant_isolation
--
-- Safe to run multiple times (IF NOT EXISTS / OR REPLACE).
-- ============================================================

BEGIN;

-- ── Extensions ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ══════════════════════════════════════════════════════════════
-- 1. organisations
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS organisations (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL,                               -- HC-4
    source_company_id   VARCHAR(100) UNIQUE,
    canonical_name      TEXT        NOT NULL,
    normalized_name     TEXT        NOT NULL,
    domain              TEXT,
    country             TEXT        NOT NULL,
    city                TEXT,
    industry            TEXT,
    employee_count      INT,
    segment             TEXT,
    propensity_score    NUMERIC(5,4) DEFAULT 0.0,    -- original TAM score — never overwritten (Rule 1)
    confidence_score    NUMERIC(5,4) DEFAULT 0.0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_organisations_tenant      ON organisations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_organisations_domain      ON organisations(domain);
CREATE INDEX IF NOT EXISTS idx_organisations_country     ON organisations(country);
CREATE UNIQUE INDEX IF NOT EXISTS uq_organisations_source
    ON organisations(tenant_id, source_company_id)
    WHERE source_company_id IS NOT NULL;

-- RLS — HC-4: every row visible only to its tenant
ALTER TABLE organisations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organisations FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS organisations_tenant_isolation ON organisations;
CREATE POLICY organisations_tenant_isolation ON organisations
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ══════════════════════════════════════════════════════════════
-- 2. contacts
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS contacts (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID        NOT NULL,                           -- HC-4
    organisation_id         UUID        NOT NULL
        REFERENCES organisations(id) ON DELETE CASCADE,
    first_name              TEXT,
    last_name               TEXT,
    full_name               TEXT,
    job_title               TEXT,
    email                   TEXT,
    phone                   TEXT,
    professional_profile_url TEXT,
    lawful_basis            TEXT        NOT NULL,   -- Kenya DPA 2019 requirement
    status                  TEXT        NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active', 'suppressed', 'unverified')),
    confidence              NUMERIC(5,4) DEFAULT 0.0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contacts_tenant          ON contacts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_organisation    ON contacts(organisation_id);
CREATE INDEX IF NOT EXISTS idx_contacts_status          ON contacts(status);

-- RLS — HC-4
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS contacts_tenant_isolation ON contacts;
CREATE POLICY contacts_tenant_isolation ON contacts
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ══════════════════════════════════════════════════════════════
-- 3. evidence  (cryptographic provenance ledger — APPEND ONLY)
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS evidence (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL,                               -- HC-4
    organisation_id     UUID        REFERENCES organisations(id) ON DELETE CASCADE,
    contact_id          UUID        REFERENCES contacts(id) ON DELETE CASCADE,
    field_name          TEXT        NOT NULL,
    observed_value      TEXT        NOT NULL,
    source_type         TEXT        NOT NULL,   -- e.g. 'public_web', 'dns_mx'
    source_url          TEXT        NOT NULL,
    extraction_method   TEXT        NOT NULL,
    confidence          NUMERIC(5,4) NOT NULL,
    observed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- HC-6 compliant: content_hash is HMAC-SHA256(field:value:url:method)
    -- using MEMBER_HMAC_SECRET from OpenBao i3/crm/hmac-secret.
    -- The application layer computes this; raw SHA-256 is rejected.
    content_hash        TEXT        NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_evidence_tenant          ON evidence(tenant_id);
CREATE INDEX IF NOT EXISTS idx_evidence_contact         ON evidence(contact_id);
CREATE INDEX IF NOT EXISTS idx_evidence_organisation    ON evidence(organisation_id);
CREATE INDEX IF NOT EXISTS idx_evidence_field           ON evidence(field_name);

-- RLS — HC-4: read isolation + append-only (no UPDATE/DELETE allowed)
ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS evidence_tenant_isolation ON evidence;
CREATE POLICY evidence_tenant_isolation ON evidence
    FOR SELECT
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS evidence_insert_policy ON evidence;
CREATE POLICY evidence_insert_policy ON evidence
    FOR INSERT
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- No UPDATE or DELETE policies → operations forbidden for all roles
-- (append-only provenance ledger by design — Rule 1)

-- ══════════════════════════════════════════════════════════════
-- 4. suppression_records
--    HC-6: email_hash and phone_hash MUST be keyed HMAC-SHA256.
--    The application enforces this; the DB stores the 64-char hex output.
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS suppression_records (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL,                               -- HC-4
    -- HC-6: 64-char hex HMAC-SHA256 keyed with MEMBER_HMAC_SECRET from OpenBao.
    -- Raw SHA-256 hashes are NOT accepted (rainbow-table vulnerable).
    email_hmac          VARCHAR(64) UNIQUE,
    phone_hmac          VARCHAR(64),
    organisation_id     UUID        REFERENCES organisations(id),
    reason              TEXT        NOT NULL,   -- 'GDPR_ERASURE' | 'OPTED_OUT' | 'DPA_SUPPRESSED'
    suppressed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_suppression_tenant       ON suppression_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_suppression_email_hmac   ON suppression_records(email_hmac);
CREATE INDEX IF NOT EXISTS idx_suppression_phone_hmac   ON suppression_records(phone_hmac)
    WHERE phone_hmac IS NOT NULL;

-- RLS — HC-4
ALTER TABLE suppression_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppression_records FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS suppression_records_tenant_isolation ON suppression_records;
CREATE POLICY suppression_records_tenant_isolation ON suppression_records
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

COMMIT;

-- ── Verification queries ──────────────────────────────────────
-- Run after applying this migration to confirm HC-4 + RLS:
--
-- SELECT tablename, rowsecurity, forcerowsecurity
--   FROM pg_tables
--  WHERE schemaname = 'public'
--    AND tablename IN ('organisations','contacts','evidence','suppression_records');
-- Expected: rowsecurity=true, forcerowsecurity=true for all 4.
--
-- SELECT COUNT(*) AS rls_policies
--   FROM pg_policies
--  WHERE tablename IN ('organisations','contacts','evidence','suppression_records')
--    AND qual LIKE '%NULLIF%';
-- Expected: 5 (organisations:1, contacts:1, evidence:2, suppression_records:1)
