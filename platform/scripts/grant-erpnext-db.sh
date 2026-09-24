#!/bin/sh
# SCRUBBED (STEP-P1-01): hardcoded MariaDB root password removed.
# Retrieve at runtime via OpenBao:
#   MARIADB_ROOT_PW=$(vault kv get -field=password i3/mariadb/root)
#   ERPNEXT_DB_PW=$(vault kv get -field=password i3/erpnext/db)
MARIADB_ROOT_PW="${MARIADB_ROOT_PW:-$(vault kv get -field=password i3/mariadb/root 2>/dev/null)}"
ERPNEXT_DB_PW="${ERPNEXT_DB_PW:-$(vault kv get -field=password i3/erpnext/db 2>/dev/null)}"
if [ -z "$MARIADB_ROOT_PW" ] || [ -z "$ERPNEXT_DB_PW" ]; then
  echo "ERROR: required passwords not set — check OpenBao paths i3/mariadb/root and i3/erpnext/db" >&2; exit 1
fi
mysql -u root --password="$MARIADB_ROOT_PW" -e "CREATE DATABASE IF NOT EXISTS \`_dadd04c55254b9ac\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS '_dadd04c55254b9ac'@'%' IDENTIFIED BY '$ERPNEXT_DB_PW'; GRANT ALL PRIVILEGES ON \`_dadd04c55254b9ac\`.* TO '_dadd04c55254b9ac'@'%'; FLUSH PRIVILEGES;" 2>&1
echo "Grant done"
