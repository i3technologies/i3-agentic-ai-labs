#!/bin/sh
# SCRUBBED (STEP-P1-01): hardcoded MariaDB root and Frappe passwords removed.
# Retrieve at runtime via OpenBao:
#   MARIADB_ROOT_PW=$(vault kv get -field=password i3/mariadb/root)
#   FRAPPE_DB_PW=$(vault kv get -field=password i3/erpnext/frappe-db)
MARIADB_ROOT_PW="${MARIADB_ROOT_PW:-$(vault kv get -field=password i3/mariadb/root 2>/dev/null)}"
FRAPPE_DB_PW="${FRAPPE_DB_PW:-$(vault kv get -field=password i3/erpnext/frappe-db 2>/dev/null)}"
if [ -z "$MARIADB_ROOT_PW" ] || [ -z "$FRAPPE_DB_PW" ]; then
  echo "ERROR: required passwords not set — check OpenBao paths" >&2; exit 1
fi
mysql -u root --password="$MARIADB_ROOT_PW" -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$MARIADB_ROOT_PW'; ALTER USER 'frappe'@'%' IDENTIFIED BY '$FRAPPE_DB_PW'; FLUSH PRIVILEGES;"
echo "Password reset done"
