#!/usr/bin/env bash
set -euo pipefail

echo "== n8n precheck: host and repo baseline =="
echo "timestamp=$(date -u +%FT%TZ)"
echo "cwd=$(pwd)"
echo "user=$(whoami)"
echo

echo "-- hostnamectl --"
hostnamectl || true
echo

echo "-- git status --"
git -C /opt/control-plane status --short || true
echo

echo "-- recent git log --"
git -C /opt/control-plane log --oneline -n 10 || true
echo

echo "-- repo files --"
find /opt/control-plane -maxdepth 3 -type f | sort || true
echo

echo "-- listening tcp ports --"
ss -lntp || true
