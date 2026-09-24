#!/bin/bash
# Create EvalOS users in Keycloak i3 realm + EvalOS DB
KC=http://localhost:8080/auth
ADMIN_PW="$1"

TOKEN=$(curl -sf -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=$ADMIN_PW" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
echo "Token OK (${#TOKEN} chars)"

create_user() {
  local REALM="$1"
  local FNAME="$2"
  local LNAME="$3"
  local EMAIL="$4"
  local USERNAME="$5"
  local PASSWORD="$6"

  # Check if user exists
  COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" \
    "$KC/admin/realms/$REALM/users?username=$USERNAME&exact=true" \
    | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')

  if [ "$COUNT" = "0" ]; then
    HTTP=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$KC/admin/realms/$REALM/users" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d "{
        \"username\": \"$USERNAME\",
        \"email\": \"$EMAIL\",
        \"firstName\": \"$FNAME\",
        \"lastName\": \"$LNAME\",
        \"enabled\": true,
        \"emailVerified\": true,
        \"credentials\": [{
          \"type\": \"password\",
          \"value\": \"$PASSWORD\",
          \"temporary\": false
        }]
      }")
    echo "Created $USERNAME in $REALM (HTTP $HTTP)"
  else
    echo "User $USERNAME already exists in $REALM"
    # Still update password to ensure it's set
    UID=$(curl -sf -H "Authorization: Bearer $TOKEN" \
      "$KC/admin/realms/$REALM/users?username=$USERNAME&exact=true" \
      | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
    if [ -n "$UID" ]; then
      curl -sf -X PUT "$KC/admin/realms/$REALM/users/$UID/reset-password" \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d "{\"type\":\"password\",\"value\":\"$PASSWORD\",\"temporary\":false}"
      echo "  Password reset for $USERNAME"
    fi
  fi
}

# ── Create EvalOS users in the i3 realm ──────────────────────
echo "=== Creating EvalOS users in i3 realm ==="
create_user "i3" "Romars" "Nyambura Marigi" "romarsn@i3technologies.co.ke" "romarsn@i3technologies.co.ke" 'REDACTED-user-password'
create_user "i3" "Becky"  "Cheptoo Gabrielle" "beckygabrielle@i3technologies.co.ke" "beckygabrielle@i3technologies.co.ke" 'REDACTED-user-password'

# ── Verify users exist ────────────────────────────────────────
echo "=== Verifying users ==="
curl -sf -H "Authorization: Bearer $TOKEN" "$KC/admin/realms/i3/users?max=50" \
  | python3 -c 'import sys,json; users=json.load(sys.stdin); [print(f"  {u[\"username\"]} | {u.get(\"email\",\"\")} | enabled={u[\"enabled\"]}") for u in users if u.get("email","").endswith("@i3technologies.co.ke")]'

echo "=== Done ==="
