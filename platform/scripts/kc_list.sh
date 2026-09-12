#!/bin/bash
KC=http://localhost:8080/auth
ADMIN_PW="$1"
TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$ADMIN_PW" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# List all realms
echo "=== ALL REALMS ==="
curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms" \
  | python3 -c 'import sys,json; [print(r["realm"]) for r in json.load(sys.stdin)]'

# Check i3 realm clients that include webui/hub/zuri
echo "=== i3 realm clients ==="
curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/clients?max=200" \
  | python3 -c 'import sys,json; [print(c["clientId"]) for c in json.load(sys.stdin) if not c["clientId"].startswith("realm-")]' 2>/dev/null

# Check i3-ai-lab realm clients
echo "=== i3-ai-lab realm clients ==="
curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3-ai-lab/clients?max=200" \
  | python3 -c 'import sys,json; [print(c["clientId"]) for c in json.load(sys.stdin) if not c["clientId"].startswith("realm-")]' 2>/dev/null
