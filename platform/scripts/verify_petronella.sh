#!/bin/bash
# STEP-P1-01: Hardcoded Keycloak admin credential removed.
# Credential is retrieved from OpenBao at runtime.
# Prerequisites: vault CLI configured, i3/keycloak/admin populated.
#
# Usage:
#   sh verify_petronella.sh
set -e

KC_ADMIN_PASS=$(vault kv get -field=password i3/keycloak/admin)
if [ -z "$KC_ADMIN_PASS" ]; then
  echo "ERROR: Could not retrieve i3/keycloak/admin from OpenBao" >&2
  exit 1
fi

TOKEN=$(curl -s -X POST http://localhost:8080/auth/realms/master/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=${KC_ADMIN_PASS}&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s "http://localhost:8080/auth/admin/realms/i3/users/649c3d42-8a1d-4ffd-be45-0867ddf9178c" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; u=json.load(sys.stdin); print('username:',u['username'],'enabled:',u['enabled'],'emailVerified:',u['emailVerified'])"
