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
  local preferred_network="verity_network"
  local id
  local name
  local networks
  local -a candidates=()
  local -a network_matches=()
  local -a candidate_descriptions=()

  mapfile -t candidates < <(docker_cmd ps --filter 'ancestor=docker.n8n.io/n8nio/n8n' --format '{{.ID}}')

  if [[ "${#candidates[@]}" -eq 0 ]]; then
    mapfile -t candidates < <(docker_cmd ps --format '{{.ID}} {{.Names}}' | awk '$2 ~ /(^|[-_])n8n($|[-_])|n8n/ {print $1}')
  fi

  if [[ "${#candidates[@]}" -eq 0 ]]; then
    echo "ERROR: could not detect a running n8n container" >&2
    echo "Running containers:" >&2
    docker_cmd ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' >&2
    exit 1
  fi

  for id in "${candidates[@]}"; do
    name="$(docker_cmd inspect "${id}" --format '{{.Name}}')"
    name="${name#/}"
    networks="$(docker_cmd inspect "${id}" --format '{{range $k, $v := .NetworkSettings.Networks}}{{printf "%s " $k}}{{end}}')"
    candidate_descriptions+=("${name} [${networks:-no-networks}]")
    case " ${networks} " in
      *" ${preferred_network} "*) network_matches+=("${name}") ;;
    esac
  done

  if [[ "${#network_matches[@]}" -eq 1 ]]; then
    printf '%s\n' "${network_matches[0]}"
    return 0
  fi

  if [[ "${#network_matches[@]}" -gt 1 ]]; then
    echo "ERROR: multiple n8n candidates found on ${preferred_network}" >&2
    printf 'Candidates: %s\n' "${network_matches[@]}" >&2
    exit 1
  fi

  if [[ "${#candidates[@]}" -eq 1 ]]; then
    echo "WARN: using sole n8n candidate outside ${preferred_network}" >&2
    printf '%s\n' "${candidate_descriptions[0]%% \[*}"
    return 0
  fi

  echo "ERROR: multiple n8n candidates found and none matched ${preferred_network}" >&2
  printf 'Candidates: %s\n' "${candidate_descriptions[@]}" >&2
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
