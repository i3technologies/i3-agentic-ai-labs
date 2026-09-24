#!/bin/sh
# SCRUBBED (STEP-P1-01): hardcoded MariaDB root password removed.
# Retrieve at runtime via OpenBao:
#   MARIADB_ROOT_PW=$(vault kv get -field=password i3/mariadb/root)
# NOTE: This script sets the root password — it must be run with the CURRENT
#       root password before rotation. After rotation update OpenBao.
MARIADB_ROOT_PW="${MARIADB_ROOT_PW:-$(vault kv get -field=password i3/mariadb/root 2>/dev/null)}"
if [ -z "$MARIADB_ROOT_PW" ]; then
  echo "ERROR: MARIADB_ROOT_PW not set — check OpenBao path i3/mariadb/root" >&2; exit 1
fi

echo "==> Current root users:"
mysql -u root --password="$MARIADB_ROOT_PW" -e "SELECT user,host FROM mysql.user WHERE user='root';" 2>&1

echo "==> Updating localhost root password..."
mysql -u root --password="$MARIADB_ROOT_PW" -e "
  ALTER USER 'root'@'localhost' IDENTIFIED BY '$MARIADB_ROOT_PW';
  FLUSH PRIVILEGES;
" 2>&1
echo "==> localhost password updated"

echo "==> Granting root@% ..."
mysql -u root --password="$MARIADB_ROOT_PW" -e "
  CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '$MARIADB_ROOT_PW';
  GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
  FLUSH PRIVILEGES;
" 2>&1
echo "==> root@% granted"
