-- ============================================================
-- <service_name> Schema — i3 DDD Domain Service
-- HC-4: tenant_id UUID NOT NULL on every table
-- HC-4: Row-Level Security enforced per tenant
-- ============================================================

-- Enable pg_crypto for UUIDv7-compatible generation (if available)
-- Else use gen_random_uuid() from pgcrypto or uuid-ossp

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Main domain table ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS resources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,                  -- HC-4: never nullable
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    -- TODO: add domain-specific columns here
);

-- ── Index on tenant_id for RLS scan performance ───────────
CREATE INDEX IF NOT EXISTS idx_resources_tenant_id ON resources (tenant_id);

-- ── Row-Level Security ────────────────────────────────────
ALTER TABLE resources ENABLE ROW LEVEL SECURITY;

-- Isolation policy: each query only sees its own tenant rows
CREATE POLICY tenant_isolation ON resources
    USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- ── Audit / updated_at trigger ────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_resources_updated_at
BEFORE UPDATE ON resources
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
