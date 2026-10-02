-- ============================================================
-- Migration: 003_indexes_and_triggers.sql
-- Extends 001_initial_schema.sql with performance optimisations,
-- an updated_at trigger, and a CloudNativePG publication for
-- logical replication read replicas.
--
-- HC-4: No new columns — tenant_id already enforced in 001.
-- HC-6: No PII columns touched here.
-- Safe to run multiple times (IF NOT EXISTS / OR REPLACE).
-- ============================================================

BEGIN;

-- ── updated_at auto-update trigger ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_organisations_updated_at'
    ) THEN
        CREATE TRIGGER trg_organisations_updated_at
            BEFORE UPDATE ON organisations
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_contacts_updated_at'
    ) THEN
        CREATE TRIGGER trg_contacts_updated_at
            BEFORE UPDATE ON contacts
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;

-- ── Partial indexes for hot query paths ──────────────────────────────────────

-- Active contacts only — the vast majority of queries filter on status='active'
CREATE INDEX IF NOT EXISTS idx_contacts_active_tenant
    ON contacts(tenant_id, organisation_id)
    WHERE status = 'active';

-- Unverified contacts queued for the verify worker
CREATE INDEX IF NOT EXISTS idx_contacts_unverified
    ON contacts(tenant_id, created_at)
    WHERE status = 'unverified';

-- Evidence by observed_at for time-range provenance queries
CREATE INDEX IF NOT EXISTS idx_evidence_observed_at
    ON evidence(tenant_id, observed_at DESC);

-- Organisations with high propensity score — used by export worker
CREATE INDEX IF NOT EXISTS idx_organisations_propensity
    ON organisations(tenant_id, propensity_score DESC)
    WHERE propensity_score > 0.5;

-- ── Logical replication publication (for read-replica analytics) ──────────────
-- CloudNativePG read replicas subscribe to this publication.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication WHERE pubname = 'crm_pub'
    ) THEN
        CREATE PUBLICATION crm_pub FOR TABLE
            organisations, contacts, evidence, suppression_records;
    END IF;
END $$;

-- ── GIN index on JSONB metadata (future-proofing enrichment payloads) ────────
-- Uncomment when a metadata JSONB column is added to contacts/organisations.
-- CREATE INDEX IF NOT EXISTS idx_contacts_metadata_gin ON contacts USING gin (metadata);

COMMIT;

-- ── Verification ──────────────────────────────────────────────────────────────
-- SELECT tgname, tgrelid::regclass FROM pg_trigger
--  WHERE tgname LIKE 'trg_%_updated_at';
-- Expected: 2 rows (organisations, contacts)
--
-- SELECT schemaname, tablename, indexname FROM pg_indexes
--  WHERE tablename IN ('contacts','organisations','evidence')
--    AND indexname LIKE '%active%' OR indexname LIKE '%unverified%'
--       OR indexname LIKE '%propensity%';
