#!/bin/sh
# SCRUBBED (STEP-P1-01): hardcoded MariaDB root password removed.
# Retrieve at runtime: MARIADB_ROOT_PW=$(vault kv get -field=password i3/mariadb/root)
MARIADB_ROOT_PW="${MARIADB_ROOT_PW:-$(vault kv get -field=password i3/mariadb/root 2>/dev/null)}"
if [ -z "$MARIADB_ROOT_PW" ]; then
  echo "ERROR: MARIADB_ROOT_PW not set and OpenBao lookup failed" >&2; exit 1
fi
mysql -u root --password="$MARIADB_ROOT_PW" -e "DROP DATABASE IF EXISTS \`_dadd04c55254b9ac\`; DROP USER IF EXISTS '_dadd04c55254b9ac'@'%'; FLUSH PRIVILEGES;" 2>&1
echo "Cleanup done"
