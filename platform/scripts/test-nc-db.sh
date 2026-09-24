#!/bin/sh
php -r "
\$db = new PDO('pgsql:host=i3-postgres-pgbouncer.i3-data.svc;port=5432;dbname=social_db', 'socialapp', 'i3-Social-DB-2026!');
echo 'Connected: ' . \$db->query('SELECT current_user')->fetchColumn() . '\n';
"
