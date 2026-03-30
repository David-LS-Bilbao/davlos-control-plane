#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${1:-root-n8n-1}"
LOCAL_FILES_PATH="${2:-/root/local-files}"

docker_cmd() {
  if docker ps >/dev/null 2>&1; then
    docker "$@"
  elif sudo -n docker ps >/dev/null 2>&1; then
    sudo -n docker "$@"
  else
    echo "ERROR: no Docker access available" >&2
    exit 1
  fi
}

root_cmd() {
  if sudo -n true >/dev/null 2>&1; then
    sudo -n "$@"
  else
    echo "ERROR: no sudo -n access available" >&2
    exit 1
  fi
}

echo "== n8n precheck: inventory minimum =="
echo "timestamp=$(date -u +%FT%TZ)"
echo

echo "-- probable database backend --"
docker_cmd exec "${CONTAINER_NAME}" sh -lc 'test -f /home/node/.n8n/database.sqlite && echo SQLITE_PRESENT || echo SQLITE_NOT_FOUND'
echo

echo "-- local-files top-level counts --"
root_cmd sh -lc "test -d '${LOCAL_FILES_PATH}' && find '${LOCAL_FILES_PATH}' -maxdepth 2 -type f | wc -l || echo 0"
echo

echo "-- local-files disk usage --"
root_cmd du -sh "${LOCAL_FILES_PATH}" || true
echo

echo "-- workflow artifact hints from accessible staging docs --"
find /opt -type f -name '*.workflow.json' 2>/dev/null | sort || true
echo

echo "-- note --"
echo "Este script no exporta workflows ni inspecciona payloads o credenciales."
