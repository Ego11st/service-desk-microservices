#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --discard-demo-data ]]; then
  echo 'This resets the dedicated Compose project and deletes its container volumes.' >&2
  echo 'Current database is backed up first; host backups are retained.' >&2
  echo 'To prepare a fresh demo: bash scripts/reset-demo.sh --discard-demo-data' >&2
  exit 2
fi
mkdir -p backups
target=$(cat runtime/db-host)
case "$target" in db|db-standby) ;; *) echo 'Unexpected database route'; exit 1;; esac
backup="backups/before_reset_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T "$target" pg_dump -U postgres -d desk -Fc > "$backup"
test -s "$backup"
echo "Database copied to $backup. Resetting only this Compose project's container volumes."
docker compose down --volumes --remove-orphans
printf 'db\n' > runtime/db-host
bash scripts/start.sh
echo 'Fresh topology ready. Database rows and broker messages are reset; the dump remains in backups/.'
