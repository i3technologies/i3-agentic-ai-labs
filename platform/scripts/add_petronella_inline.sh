#!/bin/bash
# STEP-P1-01: Hardcoded Keycloak admin credential removed.
# Credential is retrieved from OpenBao at runtime.
# Prerequisites: vault CLI configured, i3/keycloak/admin populated.
#
# Usage:
#   sh add_petronella_inline.sh
set -e

KEYCLOAK_URL="http://localhost:8080/auth"
REALM="i3"
ADMIN_USER="admin"
ADMIN_PASS=$(vault kv get -field=password i3/keycloak/admin)

if [ -z "$ADMIN_PASS" ]; then
  echo "ERROR: Could not retrieve i3/keycloak/admin from OpenBao" >&2
  exit 1
fi

TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${ADMIN_USER}&password=${ADMIN_PASS}&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token acquired."

HTTP_CODE=$(curl -s -o /tmp/resp.json -w "%{http_code}" \
  -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/users" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "petronellamumbua@i3technologies.co.ke",
    "email": "petronellamumbua@i3technologies.co.ke",
    "firstName": "Petronella Mumbua",
    "lastName": "Ndolo",
    "enabled": true,
    "emailVerified": true
  }')

echo "Create HTTP: ${HTTP_CODE}"
cat /tmp/resp.json

USER_ID=$(curl -s \
  "${KEYCLOAK_URL}/admin/realms/${REALM}/users?username=petronellamumbua%40i3technologies.co.ke" \
  -H "Authorization: Bearer ${TOKEN}" \
  | python3 -c "import sys,json; u=json.load(sys.stdin); print(u[0]['id']) if u else print('NOT_FOUND')")

echo "User ID: ${USER_ID}"

if [ "$HTTP_CODE" = "409" ]; then
  echo "User already exists — ensuring enabled..."
  curl -s -o /dev/null -w "Enable HTTP: %{http_code}\n" \
    -X PUT "${KEYCLOAK_URL}/admin/realms/${REALM}/users/${USER_ID}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"enabled":true,"emailVerified":true}'
fi

echo "DONE: Petronella Mumbua Ndolo configured in realm i3."
echo "NOTE: Set the user password via Keycloak Admin UI or the reset-password API — do not hardcode passwords in scripts."
