#!/bin/bash
# Full Keycloak client registration for all i3 platform products
KC=http://localhost:8080/auth
ADMIN_PW="$1"
TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$ADMIN_PW" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
echo "Token OK (${#TOKEN} chars)"

create_client() {
  local REALM="$1"
  local PAYLOAD="$2"
  local CLIENT_ID="$3"
  # Check if exists
  COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/$REALM/clients?clientId=$CLIENT_ID" \
    | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')
  if [ "$COUNT" = "0" ]; then
    HTTP=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$KC/admin/realms/$REALM/clients" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$PAYLOAD")
    echo "Created $CLIENT_ID in $REALM (HTTP $HTTP)"
  else
    echo "EXISTS $CLIENT_ID in $REALM"
  fi
  # Return the secret
  CID=$(curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/$REALM/clients?clientId=$CLIENT_ID" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
  if [ -n "$CID" ]; then
    SECRET=$(curl -sf -X POST -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/$REALM/clients/$CID/client-secret" \
      | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))' 2>/dev/null)
    echo "  SECRET[$CLIENT_ID]=$SECRET"
  fi
}

# ── JupyterHub in i3-ai-lab realm ────────────────────────────
create_client "i3-ai-lab" '{
  "clientId":"jupyterhub","name":"JupyterHub AI Lab","enabled":true,
  "protocol":"openid-connect","publicClient":false,
  "redirectUris":["https://jupyter.i3technologies.co.ke/*","https://jupyter.i3technologies.co.ke/hub/oauth_callback"],
  "webOrigins":["https://jupyter.i3technologies.co.ke"],
  "standardFlowEnabled":true,"directAccessGrantsEnabled":false
}' "jupyterhub"

# ── Zuri (EvalOS) in i3 realm ────────────────────────────────
create_client "i3" '{
  "clientId":"zuri","name":"Zuri — EvalOS AI Co-worker","enabled":true,
  "protocol":"openid-connect","publicClient":false,
  "redirectUris":["https://zuri.i3technologies.co.ke/*"],
  "webOrigins":["https://zuri.i3technologies.co.ke"],
  "standardFlowEnabled":true,"directAccessGrantsEnabled":false
}' "zuri"

# ── Dawa (PMaaS) in i3 realm ─────────────────────────────────
create_client "i3" '{
  "clientId":"dawa","name":"Dawa — PMaaS AI Co-worker","enabled":true,
  "protocol":"openid-connect","publicClient":false,
  "redirectUris":["https://dawa.i3technologies.co.ke/*"],
  "webOrigins":["https://dawa.i3technologies.co.ke"],
  "standardFlowEnabled":true,"directAccessGrantsEnabled":false
}' "dawa"

# ── Nuru (Engage) in i3 realm ────────────────────────────────
create_client "i3" '{
  "clientId":"nuru","name":"Nuru — Engage AI Co-worker","enabled":true,
  "protocol":"openid-connect","publicClient":false,
  "redirectUris":["https://nuru.i3technologies.co.ke/*"],
  "webOrigins":["https://nuru.i3technologies.co.ke"],
  "standardFlowEnabled":true,"directAccessGrantsEnabled":false
}' "nuru"

# ── Mfumo (AfroERP) in i3 realm ──────────────────────────────
create_client "i3" '{
  "clientId":"mfumo","name":"Mfumo — AfroERP AI Co-worker","enabled":true,
  "protocol":"openid-connect","publicClient":false,
  "redirectUris":["https://mfumo.i3technologies.co.ke/*"],
  "webOrigins":["https://mfumo.i3technologies.co.ke"],
  "standardFlowEnabled":true,"directAccessGrantsEnabled":false
}' "mfumo"

# ── PMaaS web app in i3 realm ────────────────────────────────
create_client "i3" '{
  "clientId":"pmaas-web","name":"PMaaS Campaign Management","enabled":true,
  "protocol":"openid-connect","publicClient":false,
  "redirectUris":["https://pmaas.i3technologies.co.ke/*","https://pmaas.i3technologies.co.ke/api/auth/callback/keycloak"],
  "webOrigins":["https://pmaas.i3technologies.co.ke"],
  "standardFlowEnabled":true,"directAccessGrantsEnabled":false
}' "pmaas-web"

# ── Engage web app in i3 realm ───────────────────────────────
create_client "i3" '{
  "clientId":"engage-web","name":"i3 Engage Campaign Platform","enabled":true,
  "protocol":"openid-connect","publicClient":false,
  "redirectUris":["https://engage.i3technologies.co.ke/*","https://engage.i3technologies.co.ke/api/auth/callback/keycloak"],
  "webOrigins":["https://engage.i3technologies.co.ke"],
  "standardFlowEnabled":true,"directAccessGrantsEnabled":false
}' "engage-web"

echo "=== All clients registered ==="
