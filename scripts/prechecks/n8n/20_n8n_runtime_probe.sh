#!/usr/bin/env bash
set -euo pipefail

echo "== n8n precheck: runtime probe =="
echo "timestamp=$(date -u +%FT%TZ)"
echo

echo "-- local listeners --"
ss -lntp | grep -E '(:5678|:81|:80 |:443 )' || true
echo

echo "-- n8n loopback probe --"
curl -I --max-time 5 http://127.0.0.1:5678 || true
echo

echo "-- npm loopback probe --"
curl -I --max-time 5 http://127.0.0.1:81 || true
