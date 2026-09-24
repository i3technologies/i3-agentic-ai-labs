"""
STEP-P1-01: Hardcoded credentials removed.
Credentials are retrieved from OpenBao at runtime.

Prerequisites: vault CLI configured, i3/n8n/db populated.
Usage:
  python n8n_setpass.py
"""
import asyncio
import subprocess
import asyncpg
import bcrypt


def get_vault_secret(path: str, field: str) -> str:
    result = subprocess.run(
        ["vault", "kv", "get", f"-field={field}", path],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


async def main():
    try:
        db_password = get_vault_secret("i3/n8n/db", "password")
        new_pass    = get_vault_secret("i3/n8n/admin", "password")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"ERROR: Could not retrieve credentials from OpenBao.\n{exc.stderr}"
        )

    conn = await asyncpg.connect(
        host="i3-postgres-ha.i3-data.svc",
        port=5432,
        database="n8n",
        user="n8n",
        password=db_password,
    )

    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
    await conn.execute(
        "UPDATE public.user SET password=$1 WHERE role='global:owner'",
        hashed,
    )
    row = await conn.fetchrow(
        "SELECT id, email, role FROM public.user WHERE role='global:owner'"
    )
    print("Updated user:", dict(row))
    print("New password hash set")
    await conn.close()


asyncio.run(main())
