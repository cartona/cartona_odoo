#!/bin/bash
set -e

DB_NAME="cartona_dev"
export PGPASSWORD=odoo

echo "Waiting for PostgreSQL..."
until pg_isready -h db -U odoo > /dev/null 2>&1; do
    sleep 1
done

if ! psql -h db -U odoo -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    echo "Creating database ${DB_NAME} and installing modules..."
    odoo -c /etc/odoo/odoo.conf -d "${DB_NAME}" -i queue_job,cartona_odoo --stop-after-init --without-demo=all
else
    echo "Database ${DB_NAME} already exists, skipping install."
fi

exec odoo -c /etc/odoo/odoo.conf --workers=0
