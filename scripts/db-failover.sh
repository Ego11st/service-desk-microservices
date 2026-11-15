#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(cat runtime/db-host) = db ]] || { echo 'Already failed over'; exit 1; }
standby=$(docker compose exec -T db-standby psql -U postgres -d desk -Atc 'SELECT pg_is_in_recovery()')
[[ "$standby" = t ]] || { echo 'Replica is not in recovery mode'; exit 1; }
lsn=$(docker compose exec -T db psql -U postgres -d desk -Atc 'SELECT pg_current_wal_lsn()')
for i in {1..30}; do
  synced=$(docker compose exec -T db-standby psql -U postgres -d desk -Atc "SELECT coalesce(pg_last_wal_replay_lsn() >= '$lsn'::pg_lsn,false)")
  [[ "$synced" = t ]] && break
  sleep 1
done
[[ "$synced" = t ]] || { echo 'Replica has not caught up; aborting'; exit 1; }
echo 'Crashing primary. Its restart policy is no; the former primary must stay stopped.'
docker compose kill -s SIGKILL db
docker compose stop db
docker compose exec -T -u postgres db-standby pg_ctl -D /var/lib/postgresql/data/standby promote -w
printf 'db-standby\n' > runtime/db-host
echo 'Database route switched to the promoted standby. No automatic failover is claimed.'
docker compose exec -T db-standby psql -U postgres -d desk -c 'SELECT pg_is_in_recovery(); SELECT count(*) FROM tickets;'
python3 scripts/smoke.py
echo 'Keep db stopped. Do not run docker compose up/start db until it has been reinitialized as a replica.'
