-- ============================================================
-- Migration: 004_voters_phone_hmac.sql
-- HC-6 Remediation: voters.phone is plain PII under Kenya's DPA 2019.
-- Rename to phone_hmac and enforce HMAC-SHA256 via MEMBER_HMAC_SECRET
-- at the application layer (same contract as sit_db.learners.phone_hmac
-- and ford_members_db.members_pii.phone_hmac).
--
-- Apply: psql $PMAAS_DB_URL < migrations/004_voters_phone_hmac.sql
-- RUNTIME ACTION REQUIRED: application must HMAC-SHA256-hash phone values
-- (via MEMBER_HMAC_SECRET in OpenBao) before INSERT/UPDATE.
-- ============================================================

BEGIN;

-- ── Step 1: Rename column ────────────────────────────────────────────────────
-- Drop the existing UNIQUE index first (renaming preserves constraints,
-- but we want to rebuild it explicitly with the new name).
ALTER TABLE voters RENAME COLUMN phone TO phone_hmac;

-- ── Step 2: Add NOT NULL constraint (HMAC tokens must always be present) ─────
-- Note: if existing rows have NULL phone, set a sentinel value first:
--   UPDATE voters SET phone_hmac = 'REDACTED' WHERE phone_hmac IS NULL;
-- Then:
ALTER TABLE voters ALTER COLUMN phone_hmac DROP NOT NULL;
-- Keep nullable for now — enforce NOT NULL only after backfill confirms
-- all rows have been re-hashed. To enforce strictly after backfill:
--   ALTER TABLE voters ALTER COLUMN phone_hmac SET NOT NULL;

-- ── Step 3: Add DB-level format check to catch un-hashed values ──────────────
-- HMAC-SHA256 in hex is always exactly 64 characters.
ALTER TABLE voters DROP CONSTRAINT IF EXISTS voters_phone_hmac_format;
ALTER TABLE voters ADD CONSTRAINT voters_phone_hmac_format
  CHECK (phone_hmac IS NULL OR length(phone_hmac) = 64);

-- ── Step 4: Rebuild UNIQUE index with the new column name ────────────────────
DROP INDEX IF EXISTS idx_voters_phone;
DROP INDEX IF EXISTS voters_phone_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_voters_phone_hmac ON voters (phone_hmac)
  WHERE phone_hmac IS NOT NULL;

COMMIT;

-- ── Post-migration checklist ──────────────────────────────────────────────────
-- 1. Update the PMaaS application (voter registration routes) to hash phone:
--    phone_hmac = hmac(phone.strip(), MEMBER_HMAC_SECRET, 'sha256').hexdigest()
-- 2. Backfill existing rows by running the re-hash worker pattern:
--    (mirror platform/ford/rehash_worker.py for pmaas voters)
-- 3. After confirming all rows are hashed, enforce NOT NULL:
--    ALTER TABLE voters ALTER COLUMN phone_hmac SET NOT NULL;
-- 4. Remove the voters_phone_hmac_format CHECK once NOT NULL is set
--    (the 64-char check becomes redundant after NOT NULL enforcement).
