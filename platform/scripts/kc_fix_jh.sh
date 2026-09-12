#!/bin/bash
KC=http://localhost:8080/auth
TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$1" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Check all i3-ai-lab clients
echo "=== i3-ai-lab clients (full list) ==="
curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients" \
  | python3 -c 'import sys,json; [print(c.get("clientId"),c.get("id")) for c in json.load(sys.stdin)]' 2>/dev/null

# Force-create jupyterhub with known secret
echo "=== Creating jupyterhub in i3-ai-lab ==="
RESP=$(curl -sf -X POST "$KC/admin/realms/i3-ai-lab/clients" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "clientId":"jupyterhub",
    "name":"JupyterHub AI Lab",
    "enabled":true,
    "protocol":"openid-connect",
    "publicClient":false,
    "clientAuthenticatorType":"client-secret",
    "secret":"jh-kc-i3platform-2026-secure",
    "redirectUris":["https://jupyter.i3technologies.co.ke/*","https://jupyter.i3technologies.co.ke/hub/oauth_callback"],
    "webOrigins":["https://jupyter.i3technologies.co.ke"],
    "standardFlowEnabled":true,
    "directAccessGrantsEnabled":false
  }' -w "\nHTTP:%{http_code}")
echo "Create response: $RESP"

# Retrieve it
CID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients?clientId=jupyterhub" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "NOT_FOUND")')
echo "Final CID: $CID"

SECRET=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients/$CID/client-secret" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))' 2>/dev/null)
echo "JH_SECRET=$SECRET"
