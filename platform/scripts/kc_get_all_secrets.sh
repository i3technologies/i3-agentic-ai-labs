#!/bin/bash
KC=http://localhost:8080/auth
TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$1" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Register jupyterhub in i3 realm (consistent with all other platform clients)
JH_COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=jupyterhub" \
  | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')
if [ "$JH_COUNT" = "0" ]; then
  HTTP=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$KC/admin/realms/i3/clients" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{
      "clientId":"jupyterhub",
      "name":"JupyterHub AI Lab",
      "enabled":true,"protocol":"openid-connect","publicClient":false,
      "clientAuthenticatorType":"client-secret",
      "redirectUris":["https://jupyter.i3technologies.co.ke/*","https://jupyter.i3technologies.co.ke/hub/oauth_callback"],
      "webOrigins":["https://jupyter.i3technologies.co.ke"],
      "standardFlowEnabled":true,"directAccessGrantsEnabled":false
    }')
  echo "Created jupyterhub in i3 (HTTP $HTTP)"
else
  echo "jupyterhub already in i3"
fi

JH_CID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=jupyterhub" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
JH_SEC=$(curl -sf -X POST -H "Authorization: Bearer $TOKEN" \
  "$KC/admin/realms/i3/clients/$JH_CID/client-secret" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
echo "JH_SECRET=$JH_SEC"

# Also update Zuri OIDC provider URL to use i3 realm (not i3-evalos)
ZURI_CID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=zuri" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
ZURI_SEC=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$KC/admin/realms/i3/clients/$ZURI_CID/client-secret" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
echo "ZURI_SECRET=$ZURI_SEC"

DAWA_CID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=dawa" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
DAWA_SEC=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$KC/admin/realms/i3/clients/$DAWA_CID/client-secret" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
echo "DAWA_SECRET=$DAWA_SEC"

NURU_CID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=nuru" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
NURU_SEC=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$KC/admin/realms/i3/clients/$NURU_CID/client-secret" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
echo "NURU_SECRET=$NURU_SEC"

MFUMO_CID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=mfumo" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
MFUMO_SEC=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$KC/admin/realms/i3/clients/$MFUMO_CID/client-secret" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
echo "MFUMO_SECRET=$MFUMO_SEC"

echo "=== Done ==="
