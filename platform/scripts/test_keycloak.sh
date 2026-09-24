#!/bin/bash
# Credentials retrieved at runtime from OpenBao — no plaintext secrets in source
KEYCLOAK_ADMIN_PASSWORD=$(vault kv get -field=password i3/keycloak/admin)

TOKEN=$(curl -s -X POST http://localhost:8080/auth/realms/master/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=${KEYCLOAK_ADMIN_PASSWORD}&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

USERS=$(curl -s "http://localhost:8080/auth/admin/realms/i3/users/count" -H "Authorization: Bearer $TOKEN")
CLIENTS=$(curl -s "http://localhost:8080/auth/admin/realms/i3/clients?max=50" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json;c=json.load(sys.stdin);print(len([x for x in c if not x['clientId'].startswith('security-admin') and not x['clientId'].startswith('broker') and not x['clientId'].startswith('realm-management') and not x['clientId'].startswith('account')]))")

REALMS=$(curl -s "http://localhost:8080/auth/admin/realms" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json;print([r['realm'] for r in json.load(sys.stdin)])")

echo "Realms: $REALMS"
echo "i3 realm users: $USERS"
echo "i3 realm clients (custom): $CLIENTS"

# Check specific test users
for EMAIL in "petronellamumbua@i3technologies.co.ke" "romarsn@i3technologies.co.ke" "beckygabrielle@i3technologies.co.ke"; do
  STATUS=$(curl -s "http://localhost:8080/auth/admin/realms/i3/users?username=${EMAIL}&exact=true" \
    -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json;u=json.load(sys.stdin);print('enabled='+str(u[0]['enabled'])+'  verified='+str(u[0]['emailVerified'])) if u else print('NOT FOUND')")
  echo "$EMAIL: $STATUS"
done
