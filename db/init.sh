#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$APP_PASSWORD" --set=repl_password="$REPL_PASSWORD" <<'SQL'
CREATE ROLE app LOGIN PASSWORD :'app_password';
CREATE ROLE replicator REPLICATION LOGIN PASSWORD :'repl_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /schema/schema.sql
