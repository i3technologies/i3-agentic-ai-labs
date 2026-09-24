#!/bin/sh
set -e

# Credentials retrieved at runtime from OpenBao — no plaintext secrets in source
MARIADB_ROOT_PASSWORD=$(vault kv get -field=password i3/mariadb/root)
ERP_ADMIN_PASSWORD=$(vault kv get -field=password i3/erpnext/admin)

# Write common_site_config
cat > /home/frappe/frappe-bench/sites/common_site_config.json << 'EOF'
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
EOF

echo "common_site_config.json written"

# Create the site
cd /home/frappe/frappe-bench
bench new-site afroerp.i3technologies.co.ke \
  --db-root-password "${MARIADB_ROOT_PASSWORD}" \
  --admin-password "${ERP_ADMIN_PASSWORD}" \
  --no-mariadb-socket \
  2>&1 || echo "Site may already exist or error above"

echo "Installing ERPNext app..."
bench --site afroerp.i3technologies.co.ke install-app erpnext 2>&1 || echo "App install done/already installed"

echo "DONE"
