#!/bin/sh
set -eu
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  until pg_isready -h db -p 5432; do sleep 2; done
  pg_basebackup --dbname="host=db port=5432 user=replicator application_name=standby1" \
    --pgdata="$PGDATA" --wal-method=stream --write-recovery-conf --progress
fi
exec postgres -c hot_standby=on -c hba_file=/etc/postgresql/pg_hba.conf
