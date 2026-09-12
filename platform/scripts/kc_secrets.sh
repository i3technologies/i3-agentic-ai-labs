#!/bin/bash
KC=http://localhost:8080/auth
ADMIN_PW="$1"

TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$ADMIN_PW" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "=== jupyterhub client in i3-ai-lab ==="
JH_DATA=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients?clientId=jupyterhub")
echo "$JH_DATA" | python3 -c 'import sys,json; d=json.load(sys.stdin); c=d[0] if d else {}; print("ID:",c.get("id","")); print("Secret:",c.get("secret",""))'

# Regenerate secret for jupyterhub
JH_ID=$(echo "$JH_DATA" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
if [ -n "$JH_ID" ]; then
  NEW_JH_SECRET=$(curl -sf -X POST -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients/$JH_ID/client-secret" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
  echo "JupyterHub new secret: $NEW_JH_SECRET"

  # Also update redirect URIs to ensure they're set
  curl -sf -X PUT "$KC/admin/realms/i3-ai-lab/clients/$JH_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"redirectUris\":[\"https://jupyter.i3technologies.co.ke/*\",\"https://jupyter.i3technologies.co.ke/hub/oauth_callback\"],\"webOrigins\":[\"https://jupyter.i3technologies.co.ke\"]}"
  echo "JupyterHub redirects updated"
fi

echo "=== open-webui-sage client in i3 realm ==="
SAGE_DATA=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=open-webui-sage")
SAGE_ID=$(echo "$SAGE_DATA" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
if [ -n "$SAGE_ID" ]; then
  NEW_SAGE_SECRET=$(curl -sf -X POST -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients/$SAGE_ID/client-secret" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
  echo "Sage new secret: $NEW_SAGE_SECRET"

  curl -sf -X PUT "$KC/admin/realms/i3/clients/$SAGE_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"redirectUris\":[\"https://sage.i3technologies.co.ke/*\",\"https://sage.i3technologies.co.ke/oauth/callback\"],\"webOrigins\":[\"https://sage.i3technologies.co.ke\"]}"
  echo "Sage redirects updated"
fi

# Also register zuri in i3-evalos realm
echo "=== Checking zuri client in i3-evalos realm ==="
ZURI_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-evalos")
if [ "$ZURI_STATUS" = "200" ]; then
  ZURI_COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-evalos/clients?clientId=zuri" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')
  echo "Zuri client count in i3-evalos: $ZURI_COUNT"
else
  echo "i3-evalos realm status: $ZURI_STATUS"
fi

echo "=== Done ==="
