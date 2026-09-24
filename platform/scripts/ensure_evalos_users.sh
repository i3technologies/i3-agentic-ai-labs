#!/bin/bash
KC=http://localhost:8080/auth
ADMIN_PW="$1"

TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$ADMIN_PW" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

ensure_user() {
  local REALM="$1" FNAME="$2" LNAME="$3" EMAIL="$4" USERNAME="$5" PASSWORD="$6"
  COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" \
    "$KC/admin/realms/$REALM/users?username=$USERNAME&exact=true" \
    | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')
  if [ "$COUNT" = "0" ]; then
    HTTP=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$KC/admin/realms/$REALM/users" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d "{\"username\":\"$USERNAME\",\"email\":\"$EMAIL\",\"firstName\":\"$FNAME\",\"lastName\":\"$LNAME\",\"enabled\":true,\"emailVerified\":true,\"credentials\":[{\"type\":\"password\",\"value\":\"$PASSWORD\",\"temporary\":false}]}")
    echo "CREATED $USERNAME (HTTP $HTTP)"
  else
    echo "EXISTS  $USERNAME — resetting password"
    USER_ID=$(curl -sf -H "Authorization: Bearer $TOKEN" \
      "$KC/admin/realms/$REALM/users?username=$USERNAME&exact=true" \
      | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
    curl -sf -X PUT "$KC/admin/realms/$REALM/users/$USER_ID/reset-password" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d "{\"type\":\"password\",\"value\":\"$PASSWORD\",\"temporary\":false}"
    # Ensure enabled + emailVerified
    curl -sf -X PUT "$KC/admin/realms/$REALM/users/$USER_ID" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d "{\"enabled\":true,\"emailVerified\":true,\"firstName\":\"$FNAME\",\"lastName\":\"$LNAME\",\"email\":\"$EMAIL\"}"
    echo "  Updated $USERNAME"
  fi
}

ensure_user "i3" "Romars" "Nyambura Marigi"    "romarsn@i3technologies.co.ke"        "romarsn@i3technologies.co.ke"        'REDACTED-user-password'
ensure_user "i3" "Becky"  "Cheptoo Gabrielle"  "beckygabrielle@i3technologies.co.ke" "beckygabrielle@i3technologies.co.ke" 'REDACTED-user-password'

echo "=== i3 realm users with @i3technologies.co.ke ==="
curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/users?max=100" \
  | python3 -c '
import sys,json
users = json.load(sys.stdin)
i3 = [u for u in users if u.get("email","").endswith("@i3technologies.co.ke")]
for u in i3:
    print(u.get("firstName","")+" "+u.get("lastName",""), "|", u.get("email",""), "| enabled="+str(u["enabled"]))
'
echo "=== Done ==="
