#!/usr/bin/env python3
"""
key_rotation.py — LiteLLM Virtual Key Rotation Job
===================================================
IMP-07 / PLN-02/PLN-05 — LiteLLM Metering Spine

Runs as a Kubernetes CronJob (schedule: "0 2 1 * *" — 02:00 UTC on the 1st).

Rotation strategy (R1)
----------------------
1. For each active api_key in billing.api_keys:
   a. Issue a new virtual key via POST /key/generate (same budget parameters).
   b. Revoke the old key via POST /key/delete.
   c. Store the new plaintext key in OpenBao at the same path
      (i3/litellm/virtual-keys/<customer>/<project>) — atomic overwrite.
   d. Compute HMAC-SHA256 of the new key and write a key_rotation_log row.
   e. Update billing.api_keys: new key_hash, new litellm_key_id, status='active',
      old row marked 'rotated'.

Break-glass service account (R1)
---------------------------------
The master_key is NEVER stored in any service Secret.
It lives at OpenBao path: i3/litellm/master-key
Policy: break-glass-only (Kubernetes SA: litellm-break-glass-sa)
This script runs as that SA (projected token mounted at /var/run/secrets/vault-token).
Normal services NEVER have access to the break-glass SA token.

The master_key is used ONLY here and in virtual-keys-metering-bootstrap.sh.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import subprocess
from datetime import UTC, datetime

import asyncpg
import httpx

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("key_rotation")

# ── Credentials (injected by OpenBao agent via CronJob annotation) ────────
LITELLM_URL: str = os.environ.get("LITELLM_URL", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000")
LITELLM_MASTER_KEY: str = os.environ["LITELLM_MASTER_KEY"]   # break-glass SA only
BILLING_DB_URL: str = os.environ["LITELLM_BILLING_DB_URL"]
KEY_HMAC_SECRET: str = os.environ["KEY_HMAC_SECRET"]         # OpenBao: i3/litellm/key-hmac-secret
TENANT_ID: str = os.environ["BILLING_TENANT_ID"]
ROTATED_BY: str = os.environ.get("ROTATED_BY", "key-rotation-cronjob")

HEADERS = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}", "Content-Type": "application/json"}

ACTIVE_KEYS_QUERY = """
SELECT
    ak.id            AS api_key_id,
    ak.litellm_key_id,
    ak.key_alias,
    ak.max_budget,
    ak.budget_duration,
    p.name           AS project_name,
    c.name           AS customer_name
FROM billing.api_keys ak
JOIN billing.projects  p ON p.id = ak.project_id
JOIN billing.customers c ON c.id = p.customer_id
WHERE ak.tenant_id = $1::UUID
  AND ak.status = 'active'
ORDER BY ak.created_at;
"""

UPDATE_KEY = """
UPDATE billing.api_keys
SET key_hash        = $1,
    litellm_key_id  = $2,
    status          = 'active',
    rotated_at      = now(),
    updated_at      = now()
WHERE id = $3::UUID
  AND tenant_id = $4::UUID;
"""

INSERT_ROTATION_LOG = """
INSERT INTO billing.key_rotation_log
    (tenant_id, api_key_id, old_key_hash, new_key_hash, rotated_by, rotation_reason)
VALUES
    ($1::UUID, $2::UUID, $3, $4, $5, 'scheduled-monthly-rotation');
"""


def _hmac_key(raw_key: str) -> str:
    return hmac.new(
        KEY_HMAC_SECRET.encode(),
        raw_key.encode(),
        hashlib.sha256,
    ).hexdigest()


def _vault_put(customer_slug: str, project_slug: str, raw_key: str,
               alias: str, project_id: str, customer_id: str) -> None:
    """Write new key to OpenBao — overwrites the old value atomically."""
    subprocess.run(
        [
            "vault", "kv", "put",
            f"i3/litellm/virtual-keys/{customer_slug}/{project_slug}",
            f"api_key={raw_key}",
            f"alias={alias}",
            f"project_id={project_id}",
            f"customer_id={customer_id}",
            f"rotated_at={datetime.now(UTC).isoformat()}",
        ],
        check=True,
        capture_output=True,
    )


async def rotate_key(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    row: asyncpg.Record,
) -> None:
    alias = row["key_alias"]
    old_litellm_id = row["litellm_key_id"]
    api_key_id = str(row["api_key_id"])
    log.info(f"Rotating key: alias={alias} old_id={old_litellm_id}")

    # 1. Issue replacement key
    resp = await client.post(
        f"{LITELLM_URL}/key/generate",
        headers=HEADERS,
        json={
            "key_alias":       alias,
            "max_budget":      row["max_budget"],
            "budget_duration": row["budget_duration"],
            "metadata": {"rotated_by": ROTATED_BY, "rotation_ts": datetime.now(UTC).isoformat()},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    new_raw_key: str = data["key"]
    new_litellm_id: str = data.get("key_name") or data.get("token") or data.get("id", "")

    if not new_raw_key or new_raw_key == "null":
        raise ValueError(f"LiteLLM returned empty key for {alias}")

    # 2. Fetch old key_hash before overwriting (for the audit log)
    old_key_hash: str = await conn.fetchval(
        "SELECT key_hash FROM billing.api_keys WHERE id = $1::UUID AND tenant_id = $2::UUID",
        api_key_id, TENANT_ID,
    )
    new_key_hash = _hmac_key(new_raw_key)

    # 3. Revoke old key (best-effort — don't fail rotation if already deleted)
    try:
        del_resp = await client.post(
            f"{LITELLM_URL}/key/delete",
            headers=HEADERS,
            json={"keys": [old_litellm_id]},
            timeout=30,
        )
        del_resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.warning(f"Could not revoke old key {old_litellm_id}: {exc}")

    # 4. Store new key in OpenBao
    customer_slug = row["customer_name"].lower().replace(" ", "-")
    project_slug  = row["project_name"].lower().replace(" ", "-")
    _vault_put(customer_slug, project_slug, new_raw_key,
               alias, api_key_id, customer_slug)

    # 5. Update billing DB + write audit log (single transaction)
    async with conn.transaction():
        await conn.execute(UPDATE_KEY, new_key_hash, new_litellm_id, api_key_id, TENANT_ID)
        await conn.execute(INSERT_ROTATION_LOG,
                           TENANT_ID, api_key_id,
                           old_key_hash, new_key_hash, ROTATED_BY)

    log.info(f"Rotated: alias={alias} new_id={new_litellm_id}")


async def run_rotation() -> None:
    log.info(f"Key rotation start — tenant_id={TENANT_ID} rotated_by={ROTATED_BY}")

    pool = await asyncpg.create_pool(
        BILLING_DB_URL,
        min_size=2,
        max_size=5,
        server_settings={"app.tenant_id": TENANT_ID},
        ssl="require",
    )
    try:
        async with httpx.AsyncClient() as client:
            async with pool.acquire() as conn:
                rows = await conn.fetch(ACTIVE_KEYS_QUERY, TENANT_ID)
                log.info(f"Found {len(rows)} active keys to rotate")
                errors: list[str] = []
                for row in rows:
                    try:
                        await rotate_key(client, conn, row)
                    except Exception as exc:
                        errors.append(f"{row['key_alias']}: {exc}")
                        log.error(f"Rotation failed for {row['key_alias']}: {exc}")
                if errors:
                    log.error(f"Rotation completed with {len(errors)} error(s): {errors}")
                    raise SystemExit(1)
        log.info(f"Key rotation complete — {len(rows)} keys rotated")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_rotation())
