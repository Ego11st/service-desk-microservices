#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f runtime/db-host && $(cat runtime/db-host) = db-standby ]] || {
  echo 'Use scripts/start.sh before the first database failover.' >&2
  exit 1
}
echo 'Resuming on the promoted standby; the former primary stays stopped.'
docker compose stop db
docker compose up -d --no-deps --wait --wait-timeout 180 db-standby redis nats1 nats2 nats3
docker compose stop frontend firewall-api firewall-worker api worker
docker compose up -d --no-deps --force-recreate --wait --wait-timeout 180 api worker firewall-api firewall-worker frontend
docker compose ps --all
echo 'Open http://localhost:8080; do not start db.'
