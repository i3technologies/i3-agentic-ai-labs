Run the rotate-secrets skill to safely rotate an OpenBao KV v2 secret on the i3 platform.

Ask the user which secret path to rotate if not already specified. Valid paths:
- i3/mariadb/root          (field: password)
- i3/erpnext/admin         (field: password)
- i3/keycloak/admin        (field: password)
- i3/litellm/api-key       (field: key)
- i3/pmaas/db-url          (field: url)
- i3/ford/hmac-secret      (field: secret — 256-bit hex, HC-6)
- i3/member-hmac-secret    (field: secret — 256-bit hex, HC-6 HMAC key)

Then activate the rotate-secrets skill and follow the full 8-step rotation procedure:
1. Identify the canonical KV v2 path and field
2. Generate new secret value (openssl rand)
3. Write to OpenBao with vault kv put
4. Verify the write with vault kv get
5. Update all service consumers
6. Run HC-7 sweep — grep for old value fragments
7. Run HC-6 check if rotating an HMAC key
8. Output rotation log table (no secret values in output)

IMPORTANT: Never output the actual secret value in chat or code blocks.
