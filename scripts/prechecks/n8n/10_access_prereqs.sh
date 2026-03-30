#!/usr/bin/env bash
set -euo pipefail

echo "== n8n precheck: access prerequisites =="
echo "timestamp=$(date -u +%FT%TZ)"
echo

echo "-- groups --"
groups || true
echo

echo "-- docker socket --"
ls -l /var/run/docker.sock || true
echo

echo "-- root path access checks --"
for path in /root/docker-compose.yaml /root/n8n.env /root/local-files; do
  if stat "$path" >/dev/null 2>&1; then
    echo "ACCESS_OK $path"
  else
    echo "ACCESS_BLOCKED $path"
  fi
done
echo

echo "-- docker access check --"
if docker ps >/dev/null 2>&1; then
  echo "DOCKER_ACCESS=direct"
elif sudo -n docker ps >/dev/null 2>&1; then
  echo "DOCKER_ACCESS=sudo-noninteractive"
else
  echo "DOCKER_ACCESS=blocked"
  echo "STOP: no continuar con prechecks avanzados sin acceso Docker/root de solo lectura"
fi
