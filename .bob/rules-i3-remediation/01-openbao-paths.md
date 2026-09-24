# i3 Security & Remediation — Supplementary Rules

These rules apply only when the i3-remediation mode is active.
They supplement the global hard constraints in `.bob/rules/01-hard-constraints.md`.

---

## OpenBao KV v2 Mount Reference

All secrets on this platform use the `i3/` KV v2 mount. Never reference any other mount.

| Secret Path | Field | Consumer |
|-------------|-------|----------|
| `i3/mariadb/root` | `password` | MariaDB root access |
| `i3/erpnext/admin` | `password` | ERPNext admin user |
| `i3/keycloak/admin` | `password` | Keycloak admin console |
| `i3/litellm/api-key` | `key` | LiteLLM proxy master key |
| `i3/pmaas/db-url` | `url` | PMaaS PostgreSQL connection string |
| `i3/ford/hmac-secret` | `secret` | FORD-Asili HMAC key (HC-6) |
| `i3/member-hmac-secret` | `secret` | Member NID/phone HMAC key (HC-6) |

Retrieve at runtime with:
```bash
vault kv get -field=<field> i3/<path>
```

---

## asyncpg Remediation Pattern

When fixing a connection leak, always replace this anti-pattern:
```python
# WRONG — never do this in a handler
conn = await asyncpg.connect(DATABASE_URL)
```
With this correct pattern:
```python
# CORRECT — use the lifespan pool
async with request.app.state.pool.acquire() as conn:
    await conn.execute(...)
```

---

## Sensor Check Protocol

After every file change, run the designated sensor checks from the step's
`Sensor Checks` section in `i3-platform-atomic-execution-plan.md`.
Do not mark a step complete until ALL sensor checks return the expected result.
Use the `verify-step` skill to run checks automatically.

---

## Credential Scrub Checklist

Before closing any remediation task:
- [ ] No plaintext passwords in any Python, TypeScript, YAML, JSON, or shell file
- [ ] No base64-encoded credentials in any tracked file
- [ ] `DEV_BYPASS_AUTH=true` absent from all non-gitignored files (HC-7)
- [ ] All secrets reference environment variables or OpenBao vault paths
- [ ] `.gitignore` includes `*.env`, `.env.*`, `*secret-patch.json`, `*.env.local`
