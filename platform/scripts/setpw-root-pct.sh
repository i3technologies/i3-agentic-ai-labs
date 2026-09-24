#!/bin/sh
# Credentials retrieved at runtime from OpenBao — no plaintext secrets in source
MARIADB_ROOT_PASSWORD=$(vault kv get -field=password i3/mariadb/root)
mysql -u root -p"${MARIADB_ROOT_PASSWORD}" -e "SET PASSWORD FOR 'root'@'%' = PASSWORD('${MARIADB_ROOT_PASSWORD}'); FLUSH PRIVILEGES; SELECT user,host,authentication_string FROM mysql.user WHERE user='root';" 2>&1
echo "done"
