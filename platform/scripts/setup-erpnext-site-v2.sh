#!/bin/sh
# STEP-P1-01: Hardcoded credentials removed.
# Credentials are now retrieved from OpenBao at runtime.
# Prerequisites: vault CLI configured, i3/mariadb/root and i3/erpnext/admin populated.
#
# Usage:
#   sh setup-erpnext-site-v2.sh
#
# HC-6: credentials retrieved via vault kv get — never hardcoded.
set -e

MARIADB_ROOT_PASS=$(vault kv get -field=password i3/mariadb/root)
ERPNEXT_ADMIN_PASS=$(vault kv get -field=password i3/erpnext/admin)

if [ -z "$MARIADB_ROOT_PASS" ] || [ -z "$ERPNEXT_ADMIN_PASS" ]; then
  echo "ERROR: Could not retrieve credentials from OpenBao." >&2
  echo "Ensure i3/mariadb/root and i3/erpnext/admin are populated." >&2
  exit 1
fi

echo "==> Writing common_site_config.json"
cat > /home/frappe/frappe-bench/sites/common_site_config.json << 'SITEEOF'
{
  "db_host": "mariadb.i3-afroerp.svc.cluster.local",
  "db_port": 3306,
  "redis_cache": "redis://redis.i3-afroerp.svc.cluster.local:6379/0",
  "redis_queue": "redis://redis.i3-afroerp.svc.cluster.local:6379/1",
  "redis_socketio": "redis://redis.i3-afroerp.svc.cluster.local:6379/2",
  "socketio_port": 9000,
  "webserver_port": 8000,
  "serve_default_site": true,
  "default_site": "afroerp.i3technologies.co.ke"
}
SITEEOF

echo "==> Creating new site"
cd /home/frappe/frappe-bench
bench new-site afroerp.i3technologies.co.ke \
  --db-root-password "${MARIADB_ROOT_PASS}" \
  --admin-password "${ERPNEXT_ADMIN_PASS}" \
  --mariadb-user-host-login-scope="%" \
  2>&1

echo "==> Running migration"
bench --site afroerp.i3technologies.co.ke migrate 2>&1

echo "==> Installing ERPNext app"
bench --site afroerp.i3technologies.co.ke install-app erpnext 2>&1

echo "==> DONE"
