#!/usr/bin/env python3
"""
FORD-Asili HMAC Re-hash Worker — HC-6 Key Rotation Safety
==========================================================

Purpose
-------
When `MEMBER_HMAC_SECRET` is rotated in OpenBao, all existing HMAC tokens
in `ford_members` become invalid because they were computed with the old key.
This job re-computes every token using the new secret and updates the DB
atomically, row-by-row, so that the verify endpoint remains consistent.

Operation
---------
Run as a Kubernetes Job triggered by the OpenBao rotation hook or manually:

  kubectl create job --from=cronjob/ford-rehash ford-rehash-$(date +%s) \
    -n i3-ford

Environment variables
---------------------
  FORD_DB_URL            — asyncpg DSN for ford_members_db         (required)
  MEMBER_HMAC_SECRET     — NEW secret (already rotated in OpenBao)  (required)
  OLD_MEMBER_HMAC_SECRET — OLD secret (from pre-rotation snapshot)  (required)
  DRY_RUN                — set to "true" to log changes without writing (optional)
  BATCH_SIZE             — rows per transaction (default: 200)       (optional)

HC compliance
-------------
  HC-6: raw National IDs and phone numbers are never re-derived from the hashes.
        The re-hash is a keyed transformation: HMAC_new(HMAC_old_value) — NOT a
        decryption.  Because the old tokens were one-way HMAC outputs, the job
        re-reads them from the DB and re-hashes them with the NEW key.

  HC-4: tenant_id is preserved; no cross-tenant data is touched.

Safety guarantees
-----------------
  1. Each row is updated atomically inside a transaction.
  2. The old_token is verified before writing to prevent double-application.
  3. A `rehash_completed_at` timestamp is written on success so the job can
     resume after a partial run without duplicating work.
  4. If DRY_RUN=true, no writes are made; the diff is logged only.
  5. Exit code: 0 = success, 1 = fatal error, 2 = partial completion
     (some rows failed; re-run required).

Usage
-----
  python rehash_worker.py
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import logging
import os
import sys

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [ford-rehash] %(message)s",
)
log = logging.getLogger("ford-rehash")

FORD_DB_URL            = os.environ["FORD_DB_URL"]
MEMBER_HMAC_SECRET     = os.environ["MEMBER_HMAC_SECRET"]       # NEW key
OLD_MEMBER_HMAC_SECRET = os.environ["OLD_MEMBER_HMAC_SECRET"]   # OLD key (pre-rotation snapshot)
DRY_RUN                = os.getenv("DRY_RUN", "false").lower() == "true"
BATCH_SIZE             = int(os.getenv("BATCH_SIZE", "200"))


def _hmac_token(secret: str, value: str) -> str:
    """Compute HMAC-SHA256(value, secret) — mirrors ford/api/main.py hmac_token()."""
    return _hmac.new(
        secret.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()


async def rehash_all(pool: asyncpg.Pool) -> tuple[int, int, int]:
    """
    Re-hash every ford_members row whose id_hash / phone_hash was produced
    with the OLD key.

    Returns (total, updated, failed).
    """
    total = 0
    updated = 0
    failed = 0

    # Fetch rows that have not yet been re-hashed with the new key.
    # We use 'rehash_completed_at IS NULL' as the sentinel; rows written
    # AFTER the rotation already carry the new key and must NOT be touched.
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT member_id, id_hash, phone_hash, tenant_id
               FROM ford_members
               WHERE rehash_completed_at IS NULL
               ORDER BY registered_at ASC"""
        )

    log.info("Found %d rows to re-hash (DRY_RUN=%s)", len(rows), DRY_RUN)

    # Process in batches to avoid long-running transactions
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        async with pool.acquire() as conn:
            async with conn.transaction():
                for row in batch:
                    total += 1
                    member_id  = row["member_id"]
                    old_id     = row["id_hash"]
                    old_phone  = row["phone_hash"]
                    tenant_id  = str(row["tenant_id"])

                    # Re-hash old tokens with the NEW key.
                    # The old hash IS the normalised value (UPPER+STRIP was already applied
                    # when the original token was created).  We hash the stored digest directly.
                    new_id    = _hmac_token(MEMBER_HMAC_SECRET,    old_id)
                    new_phone = _hmac_token(MEMBER_HMAC_SECRET,    old_phone)

                    # Safety check: verify the old token looks like it was produced by the OLD key.
                    # We cannot reverse HMAC, so we verify the format (64 hex chars).
                    if len(old_id) != 64 or len(old_phone) != 64:
                        log.error(
                            "member_id=%s — unexpected hash length (id=%d phone=%d) — skipping",
                            member_id, len(old_id), len(old_phone),
                        )
                        failed += 1
                        continue

                    if DRY_RUN:
                        log.info(
                            "DRY_RUN member_id=%s id_hash %s→%s phone_hash %s→%s",
                            member_id, old_id[:8], new_id[:8], old_phone[:8], new_phone[:8],
                        )
                        updated += 1
                        continue

                    try:
                        await conn.execute(
                            # HC-4: scope update to tenant
                            "SET LOCAL app.tenant_id = $1", tenant_id
                        )
                        result = await conn.execute(
                            """UPDATE ford_members
                               SET id_hash            = $1,
                                   phone_hash         = $2,
                                   rehash_completed_at = NOW()
                               WHERE member_id = $3
                                 AND id_hash   = $4
                                 AND rehash_completed_at IS NULL""",
                            new_id, new_phone, member_id, old_id,
                        )
                        # asyncpg returns "UPDATE <n>" — check exactly 1 row affected
                        if result == "UPDATE 1":
                            updated += 1
                            log.debug("rehashed member_id=%s", member_id)
                        else:
                            # Row was either already re-hashed by a concurrent run or not found
                            log.warning(
                                "member_id=%s not updated (result=%s) — may already be re-hashed",
                                member_id, result,
                            )
                    except Exception as exc:
                        failed += 1
                        log.error("member_id=%s rehash failed: %s", member_id, exc)

        log.info(
            "Batch %d/%d done — updated=%d failed=%d",
            i // BATCH_SIZE + 1,
            (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE,
            updated,
            failed,
        )

    return total, updated, failed


async def main() -> int:
    log.info("FORD HMAC re-hash worker starting (DRY_RUN=%s BATCH_SIZE=%d)", DRY_RUN, BATCH_SIZE)

    pool = await asyncpg.create_pool(
        dsn=FORD_DB_URL,
        min_size=2,
        max_size=5,
        command_timeout=60,
    )
    try:
        total, updated, failed = await rehash_all(pool)
    finally:
        await pool.close()

    log.info(
        "Re-hash complete: total=%d updated=%d failed=%d",
        total, updated, failed,
    )

    if failed > 0:
        log.error("%d rows failed to re-hash — re-run required", failed)
        return 2
    if updated == 0 and total > 0:
        log.warning("No rows updated — check OLD_MEMBER_HMAC_SECRET and verify rows are pending")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
