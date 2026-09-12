#!/bin/bash
KC=http://localhost:8080/auth
TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$1" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

CID=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$KC/admin/realms/i3-ai-lab/clients?clientId=jupyterhub" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')

SECRET=$(curl -sf -X POST -H "Authorization: Bearer $TOKEN" \
  "$KC/admin/realms/i3-ai-lab/clients/$CID/client-secret" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("value",""))')

echo "JH_SECRET=$SECRET"
