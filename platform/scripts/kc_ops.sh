#!/bin/bash
# Keycloak operator script — register clients for jupyterhub + open-webui-sage
KC=http://localhost:8080/auth
ADMIN_PW="$1"

TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$ADMIN_PW" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "=== Token acquired (${#TOKEN} chars) ==="

# ── List existing realms ─────────────────────────────────────
echo "=== Realms ==="
curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms" \
  | python3 -c 'import sys,json; [print(r["realm"]) for r in json.load(sys.stdin)]'

# ── Create i3-ai-lab realm if missing ────────────────────────
REALM_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab")
if [ "$REALM_STATUS" = "404" ]; then
  echo "=== Creating realm i3-ai-lab ==="
  curl -sf -X POST "$KC/admin/realms" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"realm":"i3-ai-lab","enabled":true,"displayName":"i3 AI Lab","registrationAllowed":false,"loginWithEmailAllowed":true,"sslRequired":"external"}'
  echo "Realm i3-ai-lab created"
else
  echo "Realm i3-ai-lab exists (HTTP $REALM_STATUS)"
fi

# ── Register jupyterhub client in i3-ai-lab ──────────────────
JH_EXISTS=$(curl -sf -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients?clientId=jupyterhub")
JH_COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients?clientId=jupyterhub" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')
if [ "$JH_COUNT" = "0" ]; then
  echo "=== Registering jupyterhub client in i3-ai-lab ==="
  curl -sf -X POST "$KC/admin/realms/i3-ai-lab/clients" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "clientId": "jupyterhub",
      "name": "JupyterHub AI Lab",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": false,
      "redirectUris": ["https://jupyter.i3technologies.co.ke/*"],
      "webOrigins": ["https://jupyter.i3technologies.co.ke"],
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": false,
      "secret": "jupyterhub-keycloak-secret-pending-registration"
    }'
  echo "jupyterhub client created"
else
  echo "jupyterhub client already exists"
fi

# Get jupyterhub client secret
JH_ID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients?clientId=jupyterhub" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
if [ -n "$JH_ID" ]; then
  JH_SECRET=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients/$JH_ID/client-secret" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
  echo "JupyterHub client secret: $JH_SECRET"
fi

# ── Register open-webui-sage client in i3 realm ─────────────
SAGE_COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=open-webui-sage" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')
if [ "$SAGE_COUNT" = "0" ]; then
  echo "=== Registering open-webui-sage client in i3 realm ==="
  curl -sf -X POST "$KC/admin/realms/i3/clients" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "clientId": "open-webui-sage",
      "name": "Sage AI Lab Open WebUI",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": false,
      "redirectUris": ["https://sage.i3technologies.co.ke/*"],
      "webOrigins": ["https://sage.i3technologies.co.ke"],
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": false,
      "secret": "sage-keycloak-secret-pending-registration"
    }'
  echo "open-webui-sage client created"
else
  echo "open-webui-sage client already exists"
fi

# Get sage client secret
SAGE_ID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?clientId=open-webui-sage" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
if [ -n "$SAGE_ID" ]; then
  SAGE_SECRET=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients/$SAGE_ID/client-secret" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')
  echo "Sage client secret: $SAGE_SECRET"
fi

echo "=== Done ==="
