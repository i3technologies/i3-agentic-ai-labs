#!/bin/bash
# Add Petronella Mumbua Ndolo to i3 realm in Keycloak
set -e

KEYCLOAK_URL="http://localhost:8080/auth"
REALM="i3"
ADMIN_USER="$(oc get secret credential-i3-keycloak -n i3-auth -o jsonpath='{.data.ADMIN_USERNAME}' | base64 -d)"
ADMIN_PASS="$(oc get secret credential-i3-keycloak -n i3-auth -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d)"

# Get admin token
TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${ADMIN_USER}&password=${ADMIN_PASS}&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Got token."

# Create user
HTTP_CODE=$(curl -s -o /tmp/create_resp.json -w "%{http_code}" \
  -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/users" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "petronellamumbua@i3technologies.co.ke",
    "email": "petronellamumbua@i3technologies.co.ke",
    "firstName": "Petronella Mumbua",
    "lastName": "Ndolo",
    "enabled": true,
    "emailVerified": true,
    "credentials": [
      {
        "type": "password",
        "value": "REDACTED-user-password",
        "temporary": false
      }
    ]
  }')

echo "Create user HTTP: ${HTTP_CODE}"
cat /tmp/create_resp.json

if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "409" ]; then
  # Fetch user ID
  USER_ID=$(curl -s \
    "${KEYCLOAK_URL}/admin/realms/${REALM}/users?username=petronellamumbua%40i3technologies.co.ke" \
    -H "Authorization: Bearer ${TOKEN}" \
    | python3 -c "import sys,json; users=json.load(sys.stdin); print(users[0]['id']) if users else print('NOT_FOUND')")
  echo "User ID: ${USER_ID}"

  if [ "$HTTP_CODE" = "409" ]; then
    # User exists — reset password
    curl -s -o /dev/null -w "Reset password HTTP: %{http_code}\n" \
      -X PUT "${KEYCLOAK_URL}/admin/realms/${REALM}/users/${USER_ID}/reset-password" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{"type":"password","value":"REDACTED-user-password","temporary":false}'
    # Ensure enabled
    curl -s -o /dev/null -w "Enable user HTTP: %{http_code}\n" \
      -X PUT "${KEYCLOAK_URL}/admin/realms/${REALM}/users/${USER_ID}" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{"enabled":true,"emailVerified":true}'
  fi
  echo "Done. Petronella user configured."
else
  echo "ERROR creating user."
  exit 1
fi
