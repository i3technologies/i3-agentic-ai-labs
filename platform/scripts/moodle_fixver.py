"""
STEP-P1-01: Hardcoded credentials removed.
Credentials are retrieved from OpenBao at runtime.

Prerequisites: vault CLI configured, i3/edbridge/db populated.
Usage:
  python moodle_fixver.py
"""
import asyncio
import os
import subprocess
import asyncpg


def get_vault_secret(path: str, field: str) -> str:
    result = subprocess.run(
        ["vault", "kv", "get", f"-field={field}", path],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


async def main():
    try:
        db_password = get_vault_secret("i3/edbridge/db", "password")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"ERROR: Could not retrieve i3/edbridge/db from OpenBao.\n{exc.stderr}"
        )

    pool = await asyncpg.create_pool(
        host="i3-postgres-ha.i3-data.svc",
        port=5432,
        database="edbridge_db",
        user="edbridge",
        password=db_password,
        min_size=1,
        max_size=1,
    )

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT name, value FROM mdl_config WHERE name = 'version'")
            print(f"Current DB version: {row['value']}")

            await conn.execute(
                "UPDATE mdl_config SET value = '2024042212.00' WHERE name = 'version'"
            )
            row2 = await conn.fetchrow("SELECT name, value FROM mdl_config WHERE name = 'version'")
            print(f"Updated DB version: {row2['value']}")
    finally:
        await pool.close()


asyncio.run(main())
