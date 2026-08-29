#!/bin/bash
# keycloak-remove-exampleds.sh
# Called as postStart lifecycle hook to remove the H2 ExampleDS
# which causes XA recovery failures in RHSSO 7.6

set -e

MAX_WAIT=120
INTERVAL=5
elapsed=0

# Wait for WildFly management port to be ready
until curl -sf --max-time 3 http://localhost:9990/management > /dev/null 2>&1; do
    if [ $elapsed -ge $MAX_WAIT ]; then
        echo "[postStart] Management port timeout — skipping ExampleDS removal"
        exit 0
    fi
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

# Get management password
PASSWORD_FILE="/tmp/management-password"
if [ -f "$PASSWORD_FILE" ]; then
    PASSWORD=$(cat "$PASSWORD_FILE")
else
    PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)
    /opt/jboss/keycloak/bin/add-user.sh -u admin -p "$PASSWORD" > /dev/null 2>&1 || true
    echo "$PASSWORD" > "$PASSWORD_FILE"
fi

AUTH="--digest -u admin:$PASSWORD"

# Remove ExampleDS if it exists
echo "[postStart] Removing ExampleDS..."
curl -sf --max-time 10 http://localhost:9990/management $AUTH \
    --header "Content-Type: application/json" \
    -d '{"operation":"remove","address":[{"subsystem":"datasources"},{"data-source":"ExampleDS"}]}' \
    > /dev/null 2>&1 && echo "[postStart] ExampleDS removed" || echo "[postStart] ExampleDS not found or already removed"

exit 0
