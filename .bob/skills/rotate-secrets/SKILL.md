---
name: rotate-secrets
description: Step-by-step OpenBao KV v2 secret rotation procedure for the i3 platform — covers HMAC key, DB passwords, LiteLLM API keys, and Keycloak admin credentials. Use when rotating any i3/ mount secret per HC-6 and HC-7.
---

When the user requests a secret rotation:

1. **Identify the target secret** using the canonical KV v2 path schema:
   ```
   i3/mariadb/root          → { password: <value> }
   i3/erpnext/admin         → { password: <value> }
   i3/keycloak/admin        → { password: <value> }
   i3/litellm/api-key       → { key: <value> }
   i3/pmaas/db-url          → { url: "postgresql://pmaas:<value>@..." }
   i3/ford/hmac-secret      → { secret: <256-bit hex> }
   i3/member-hmac-secret    → { secret: <256-bit hex> }   ← HC-6 HMAC key
   ```

2. **Generate a new secret value** — never output the value in plain text in chat:
   - For passwords: use `openssl rand -base64 32` in terminal.
   - For HMAC secrets (HC-6): use `openssl rand -hex 32` (produces 256-bit hex).
   - For LiteLLM keys: use `openssl rand -hex 24` prefixed with `sk-i3-`.

3. **Write the new secret to OpenBao** (KV v2):
   ```bash
   vault kv put i3/<path> <field>=<new-value>
   ```
   Always use the `i3/` mount prefix. Never use a different mount.

4. **Verify the write** before updating consumers:
   ```bash
   vault kv get i3/<path>
   ```
   Confirm the `created_time` metadata timestamp reflects the rotation.

5. **Update all consumers** — search for the secret reference across the codebase:
   - Python services: environment variable injected via Kubernetes Secret or OpenBao agent injector.
   - TypeScript services: same — never hardcode in source.
   - Kubernetes manifests: patch the Secret object or re-trigger the OpenBao sidecar inject annotation.

6. **HC-7 sweep** — after rotation, scan the workspace to ensure the old value is not present:
   ```bash
   grep -r "<old-value-fragment>" . --include="*.py" --include="*.ts" --include="*.yaml" --include="*.json"
   ```
   The grep MUST return zero matches before marking the rotation complete.

7. **HC-6 check** (HMAC secrets only) — confirm all references to the HMAC key use the environment variable `MEMBER_HMAC_SECRET` and call `hmac.new(key, msg, hashlib.sha256)`, never `hashlib.sha256(raw_nid)`.

8. **Output a rotation log** (no secret values):
   | Secret Path | Rotated At | Consumers Updated | HC-7 Sweep | Status |
   |-------------|-----------|-------------------|------------|--------|
   | i3/<path>   | <timestamp> | Yes/No           | PASS/FAIL  | ✅/❌  |
