#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T firewall-api iptables -S
echo 'ALLOW: api -> PostgreSQL:5432'
docker compose exec -T api python -c 'import socket; s=socket.create_connection(("db",5432),3); print("PASS connected"); s.close()'
echo 'DENY: api -> NATS monitoring:8222 (same network, forbidden port)'
docker compose exec -T api python -c 'import socket
try:
 s=socket.create_connection(("nats1",8222),3)
except (TimeoutError, OSError):
 print("PASS blocked")
else:
 s.close(); raise SystemExit("FAIL: forbidden port is reachable")'
target=$(cat runtime/db-host)
case "$target" in db) ip=172.30.20.10;; db-standby) ip=172.30.20.11;; *) exit 1;; esac
restore_rule() {
  docker compose exec -T firewall-api iptables -D OUTPUT -p tcp -d "$ip" --dport 5432 -j DROP || true
}
trap restore_rule EXIT
echo 'Revoke a legitimate DB connection, BEFORE established-connection acceptance'
docker compose exec -T firewall-api iptables -I OUTPUT 1 -p tcp -d "$ip" --dport 5432 -j DROP
code=$(curl -s -o evidence/firewall-denied.json -w '%{http_code}' -X POST http://localhost:8080/api/tickets -H 'Content-Type: application/json' -d '{"title":"Firewall test","status":"open"}')
echo "HTTP $code (expected 503)"
[[ "$code" = 503 ]]
restore_rule
trap - EXIT
echo 'Rule restored; a new database write must succeed'
curl -fsS -X POST http://localhost:8080/api/tickets -H 'Content-Type: application/json' -d '{"title":"После восстановления firewall","status":"open"}'
printf '\n'
