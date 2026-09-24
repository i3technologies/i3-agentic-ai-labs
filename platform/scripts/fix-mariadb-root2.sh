#!/bin/sh
# STEP-P1-01: Hardcoded credentials removed.
# This script is now a wrapper that reads credentials from OpenBao at runtime.
# Prerequisites: OpenBao CLI (vault/bao) configured and authenticated.
#
# Usage:
#   sh fix-mariadb-root2.sh
#
# HC-6: credentials retrieved via vault kv get — never hardcoded.
set -e

MARIADB_ROOT_PASS=$(vault kv get -field=password i3/mariadb/root)
if [ -z "$MARIADB_ROOT_PASS" ]; then
  echo "ERROR: Could not retrieve i3/mariadb/root from OpenBao" >&2
  exit 1
fi

echo "==> Show root users:"
mysql -u root -p"${MARIADB_ROOT_PASS}" \
  -e "SELECT user,host FROM mysql.user WHERE user='root';" 2>&1

echo "==> Grant root from % range:"
mysql -u root -p"${MARIADB_ROOT_PASS}" -e \
  "CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${MARIADB_ROOT_PASS}'; \
   GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; \
   FLUSH PRIVILEGES;" 2>&1

echo "==> Done"
