#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${1:-}"
LOCAL_FILES_PATH="${2:-}"

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

detect_container_name() {
  local by_image
  local by_name

  by_image="$(docker_cmd ps --filter 'ancestor=docker.n8n.io/n8nio/n8n' --format '{{.Names}}' | head -n 1)"
  if [[ -n "${by_image}" ]]; then
    printf '%s\n' "${by_image}"
    return 0
  fi

  by_name="$(docker_cmd ps --format '{{.Names}}' | grep -E '(^|[-_])n8n($|[-_])|n8n' | head -n 1 || true)"
  if [[ -n "${by_name}" ]]; then
    printf '%s\n' "${by_name}"
    return 0
  fi

  echo "ERROR: could not detect a running n8n container" >&2
  echo "Running containers:" >&2
  docker_cmd ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' >&2
  exit 1
}

derive_local_files_path() {
  local container_name="$1"
  local mount_path

  mount_path="$(docker_cmd inspect "${container_name}" --format '{{range .Mounts}}{{if and (eq .Type "bind") (eq .Destination "/files")}}{{println .Source}}{{end}}{{end}}' | head -n 1)"
  printf '%s\n' "${mount_path}"
}

if [[ -z "${CONTAINER_NAME}" ]]; then
  CONTAINER_NAME="$(detect_container_name)"
fi

if [[ -z "${LOCAL_FILES_PATH}" ]]; then
  LOCAL_FILES_PATH="$(derive_local_files_path "${CONTAINER_NAME}")"
fi

echo "== n8n precheck: inventory minimum =="
echo "timestamp=$(date -u +%FT%TZ)"
echo "container=${CONTAINER_NAME}"
if [[ -n "${LOCAL_FILES_PATH}" ]]; then
  echo "local_files_path=${LOCAL_FILES_PATH}"
else
  echo "local_files_path=NOT_DETECTED"
fi
echo

echo "-- probable database backend --"
docker_cmd exec "${CONTAINER_NAME}" sh -lc 'test -f /home/node/.n8n/database.sqlite && echo SQLITE_PRESENT || echo SQLITE_NOT_FOUND'
echo

echo "-- local-files top-level counts --"
if [[ -n "${LOCAL_FILES_PATH}" ]]; then
  root_cmd sh -lc "test -d '${LOCAL_FILES_PATH}' && find '${LOCAL_FILES_PATH}' -maxdepth 2 -type f | wc -l || echo 0"
else
  echo "LOCAL_FILES_PATH_NOT_DETECTED"
fi
echo

echo "-- local-files disk usage --"
if [[ -n "${LOCAL_FILES_PATH}" ]]; then
  root_cmd du -sh "${LOCAL_FILES_PATH}" || true
else
  echo "LOCAL_FILES_PATH_NOT_DETECTED"
fi
echo

echo "-- workflow artifact hints from accessible staging docs --"
find /opt -type f -name '*.workflow.json' 2>/dev/null | sort || true
echo

echo "-- note --"
echo "Este script no exporta workflows ni inspecciona payloads o credenciales."
