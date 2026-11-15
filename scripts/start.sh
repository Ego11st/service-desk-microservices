#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/init-env.sh
if [[ $(cat runtime/db-host) != db ]]; then
  echo 'A manual database failover has occurred. Do not start the former primary.' >&2
  echo 'Read README.md: work continues on db-standby; rejoin requires rebuilding the old primary.' >&2
  exit 1
fi
docker compose version
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 240
docker compose ps
echo 'Open http://localhost:8080'
