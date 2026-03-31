#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${1:-}"

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

get_env_value() {
  local key="$1"

  docker_cmd inspect "${CONTAINER_NAME}" --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | awk -F= -v key="${key}" '$1 == key {sub(/^[^=]*=/, "", $0); print; exit}'
}

has_env_key() {
  local key="$1"

  if docker_cmd inspect "${CONTAINER_NAME}" --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | cut -d= -f1 \
    | grep -qx "${key}"; then
    echo "yes"
  else
    echo "no"
  fi
}

if [[ -z "${CONTAINER_NAME}" ]]; then
  CONTAINER_NAME="$(detect_container_name)"
fi

DB_TYPE_VALUE="$(get_env_value "DB_TYPE" || true)"
HAS_DB_POSTGRESDB_HOST="$(has_env_key "DB_POSTGRESDB_HOST")"
HAS_DB_POSTGRESDB_PORT="$(has_env_key "DB_POSTGRESDB_PORT")"
HAS_DB_POSTGRESDB_DATABASE="$(has_env_key "DB_POSTGRESDB_DATABASE")"
HAS_DB_POSTGRESDB_USER="$(has_env_key "DB_POSTGRESDB_USER")"

echo "== n8n precheck: db backend readonly =="
echo "timestamp=$(date -u +%FT%TZ)"
echo "container=${CONTAINER_NAME}"
echo

echo "-- db env evidence --"
if [[ -n "${DB_TYPE_VALUE}" ]]; then
  echo "DB_TYPE=${DB_TYPE_VALUE}"
else
  echo "DB_TYPE=NOT_SET"
fi
echo "DB_POSTGRESDB_HOST_PRESENT=${HAS_DB_POSTGRESDB_HOST}"
echo "DB_POSTGRESDB_PORT_PRESENT=${HAS_DB_POSTGRESDB_PORT}"
echo "DB_POSTGRESDB_DATABASE_PRESENT=${HAS_DB_POSTGRESDB_DATABASE}"
echo "DB_POSTGRESDB_USER_PRESENT=${HAS_DB_POSTGRESDB_USER}"
echo

echo "-- sqlite artifact evidence --"
docker_cmd exec "${CONTAINER_NAME}" sh -lc '
if test -f /home/node/.n8n/database.sqlite; then
  echo "SQLITE_PRESENT=yes"
  if command -v stat >/dev/null 2>&1; then
    echo "SQLITE_SIZE_BYTES=$(stat -c %s /home/node/.n8n/database.sqlite)"
    echo "SQLITE_MTIME=$(stat -c %y /home/node/.n8n/database.sqlite)"
  else
    echo "SQLITE_SIZE_BYTES=$(wc -c </home/node/.n8n/database.sqlite | tr -d " ")"
    echo "SQLITE_MTIME=STAT_UNAVAILABLE"
  fi
else
  echo "SQLITE_PRESENT=no"
fi
'
echo

if [[ "${DB_TYPE_VALUE}" == "postgresdb" || "${DB_TYPE_VALUE}" == "postgres" ]]; then
  if [[ "${HAS_DB_POSTGRESDB_HOST}" == "yes" && "${HAS_DB_POSTGRESDB_PORT}" == "yes" && "${HAS_DB_POSTGRESDB_DATABASE}" == "yes" && "${HAS_DB_POSTGRESDB_USER}" == "yes" ]]; then
    echo "RUNTIME_DB_HINT=POSTGRES_SELECTED"
  else
    echo "RUNTIME_DB_HINT=INCONCLUSIVE"
  fi
elif [[ "${DB_TYPE_VALUE}" == "sqlite" ]]; then
  echo "RUNTIME_DB_HINT=SQLITE_SELECTED"
else
  echo "RUNTIME_DB_HINT=INCONCLUSIVE"
fi
