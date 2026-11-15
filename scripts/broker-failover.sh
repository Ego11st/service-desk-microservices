#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
leader=$(curl -fsS http://localhost:8080/api/diagnostics | python3 -c 'import sys,json; print(json.load(sys.stdin)["broker"]["leader"])')
case "$leader" in nats1|nats2|nats3) ;; *) echo 'Stream leader is not ready'; exit 1;; esac
echo "Crashing stream leader: $leader"
trap 'docker compose start "$leader"' EXIT
docker compose kill -s SIGKILL "$leader"
echo 'Waiting for election among the two remaining replicas'
sleep 5
python3 scripts/smoke.py
echo 'The test passed with one broker node down. Diagnostics above shows the new leader.'
docker compose start "$leader"
trap - EXIT
