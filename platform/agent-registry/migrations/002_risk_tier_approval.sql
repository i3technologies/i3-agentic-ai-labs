-- ============================================================
-- Agent Registry — Migration 002
-- Adds risk_tier (0–3) and approval_policy columns.
-- Idempotent: all statements use IF NOT EXISTS / DO $$ guards.
-- Rollback: see ROLLBACK section at the bottom.
-- HC-4: tenant_id already present from 001_init.sql
-- ============================================================

-- ── Add risk_tier column (default 1 = low-risk) ───────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_registry' AND column_name = 'risk_tier'
    ) THEN
        ALTER TABLE agent_registry
            ADD COLUMN risk_tier SMALLINT NOT NULL DEFAULT 1
                CHECK (risk_tier BETWEEN 0 AND 3);
    END IF;
END $$;

-- ── Add approval_policy column ────────────────────────────
-- Values: 'auto' (tier 0/1/2 auto-approve),
--         'human_required' (tier 3+ must have signed record)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_registry' AND column_name = 'approval_policy'
    ) THEN
        ALTER TABLE agent_registry
            ADD COLUMN approval_policy TEXT NOT NULL DEFAULT 'auto'
                CHECK (approval_policy IN ('auto', 'human_required'));
    END IF;
END $$;

-- ── Index for tier-based queries ──────────────────────────
CREATE INDEX IF NOT EXISTS idx_agent_registry_risk_tier
    ON agent_registry (risk_tier);

-- ── Patch existing rows: risk_tier=3 → approval_policy='human_required'
-- (Safe to re-run; has no effect if already set.)
UPDATE agent_registry
   SET approval_policy = 'human_required'
 WHERE risk_tier >= 3
   AND approval_policy = 'auto';

-- ============================================================
-- ROLLBACK (manual — run if migration must be undone):
--
--   ALTER TABLE agent_registry DROP COLUMN IF EXISTS approval_policy;
--   ALTER TABLE agent_registry DROP COLUMN IF EXISTS risk_tier;
--   DROP INDEX IF EXISTS idx_agent_registry_risk_tier;
--
-- Impact: risk_tier / approval_policy metadata is lost; gateway
--   falls back to autonomy_tier checks only (HC-3 still enforced).
-- ============================================================
