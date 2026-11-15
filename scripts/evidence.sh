#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p evidence
docker compose ps --all > evidence/containers.txt
docker compose images > evidence/images.txt
docker compose exec -T firewall-api iptables -S > evidence/firewall-api.txt
docker compose exec -T firewall-worker iptables -S > evidence/firewall-worker.txt
docker compose exec -T db-standby psql -U postgres -d desk -c 'SELECT pg_is_in_recovery(),pg_last_wal_replay_lsn();' > evidence/replica.txt
curl -fsS http://localhost:8080/api/diagnostics > evidence/diagnostics.json
docker compose logs --tail=30 api worker > evidence/events.txt
python3 scripts/smoke.py | tee evidence/functional.txt
echo 'Evidence files saved. Make screenshots of terminal output and the browser for your slides.'
