#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
target=$(cat runtime/db-host)
stamp=$(date +%Y%m%d_%H%M%S)
backup="backups/desk_${stamp}.dump"
restore_db="verify_${stamp}"
docker compose exec -T "$target" pg_dump -U postgres -d desk -Fc > "$backup"
test -s "$backup"
docker compose exec -T "$target" createdb -U postgres "$restore_db"
docker compose exec -T "$target" pg_restore -U postgres -d "$restore_db" --exit-on-error < "$backup"
echo "Backup: $backup; restored independently to $restore_db"
docker compose exec -T "$target" psql -U postgres -d "$restore_db" -c 'SELECT count(*) AS restored_tickets FROM tickets; SELECT count(*) AS restored_notifications FROM notifications;'
echo 'Compare these counts with the source while nobody writes to it:'
docker compose exec -T "$target" psql -U postgres -d desk -c 'SELECT count(*) AS source_tickets FROM tickets; SELECT count(*) AS source_notifications FROM notifications;'
echo 'Verification database and dump are retained. The application database was not overwritten.'
