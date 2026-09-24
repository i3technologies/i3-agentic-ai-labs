-- ============================================================
-- Migration 004: FORD HMAC re-hash support column
-- Applies to: ford_members_db
-- Idempotent: uses IF NOT EXISTS / ALTER COLUMN IF NOT EXISTS guards.
-- ============================================================

-- Add sentinel column so the rehash_worker can skip rows already processed
-- and so concurrent re-hash runs are idempotent.
ALTER TABLE ford_members
  ADD COLUMN IF NOT EXISTS rehash_completed_at TIMESTAMPTZ;

-- Index lets the worker quickly find pending rows without a full-table scan.
CREATE INDEX IF NOT EXISTS idx_ford_members_rehash_pending
  ON ford_members (registered_at ASC)
  WHERE rehash_completed_at IS NULL;

-- Comment documents the rotation procedure for operators.
COMMENT ON COLUMN ford_members.rehash_completed_at IS
  'Set by rehash_worker.py when MEMBER_HMAC_SECRET is rotated (HC-6). '
  'NULL = hashed with current key; NOT NULL = already re-hashed.';
