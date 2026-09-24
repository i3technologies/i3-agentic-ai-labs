#!/bin/sh
set -e
echo "==> Installing Moodle 4.4 via git..."
cd /tmp

# Download Moodle 4.4 stable
git clone --depth=1 --branch=MOODLE_404_STABLE https://github.com/moodle/moodle.git /tmp/moodle-src 2>&1 || {
  echo "git clone failed - trying direct download"
  exit 1
}

echo "==> Copying Moodle to /var/www/html..."
cp -r /tmp/moodle-src/. /var/www/html/
rm -rf /tmp/moodle-src

echo "==> Setting permissions..."
chown -R www-data:www-data /var/www/html/ 2>/dev/null || true
chmod -R 755 /var/www/html/

echo "==> Running Moodle CLI installer..."
php /var/www/html/admin/cli/install.php \
  --chmod=2777 \
  --lang=en \
  --wwwroot=https://moodle.i3technologies.co.ke \
  --dataroot=/var/www/moodledata \
  --dbtype=pgsql \
  --dbhost=i3-postgres-pgbouncer.i3-data.svc \
  --dbport=5432 \
  --dbname=edbridge_db \
  --dbuser=edbridge \
  --dbpass=REDACTED-edbridge-db \
  --dbprefix=mdl_ \
  --fullname=i3EduBridge \
  --shortname=i3edu \
  --summary="i3 Technologies AI-Powered Learning Platform" \
  --adminuser=i3admin \
  --adminpass=i3-Moodle-Admin-2026! \
  --adminemail=admin@i3technologies.co.ke \
  --non-interactive \
  --agree-license 2>&1

echo "==> DONE"
