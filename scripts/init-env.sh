#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p runtime evidence backups
if [[ ! -f .env ]]; then
  umask 077
  for key in POSTGRES_PASSWORD APP_PASSWORD REPL_PASSWORD REDIS_PASSWORD NATS_TOKEN; do
    value=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
    printf '%s=%s\n' "$key" "$value" >> .env
  done
  echo '.env created with random passwords'
fi
[[ -f runtime/db-host ]] || printf 'db\n' > runtime/db-host
chmod 644 runtime/db-host
