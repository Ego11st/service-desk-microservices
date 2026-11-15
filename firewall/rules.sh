#!/bin/sh
set -eu
# These rules affect only the network namespace shared with api or worker.
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT
iptables -F INPUT
iptables -F OUTPUT
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -p udp --dport 53 -d 127.0.0.11 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -d 127.0.0.11 -j ACCEPT
for addr in 172.30.20.10 172.30.20.11; do
  iptables -A OUTPUT -p tcp -d "$addr" --dport 5432 -j ACCEPT
done
for addr in 172.30.40.10 172.30.40.11 172.30.40.12; do
  iptables -A OUTPUT -p tcp -d "$addr" --dport 4222 -j ACCEPT
done
if [ "${ROLE:-api}" = api ]; then
  iptables -A INPUT -p tcp -s 172.30.10.10 --dport 8000 -j ACCEPT
  iptables -A OUTPUT -p tcp -d 172.30.30.10 --dport 6379 -j ACCEPT
fi
iptables -P INPUT DROP
iptables -P OUTPUT DROP
touch /tmp/ready
echo "Firewall active for ${ROLE:-api}"
trap 'exit 0' TERM INT
while :; do sleep 3600 & wait $!; done
