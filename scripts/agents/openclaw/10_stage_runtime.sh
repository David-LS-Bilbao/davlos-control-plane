#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

RUNTIME_ROOT="/opt/automation/agents/openclaw"
COMPOSE_DIR="${RUNTIME_ROOT}/compose"
CONFIG_DIR="${RUNTIME_ROOT}/config"
STATE_DIR="${RUNTIME_ROOT}/state"
LOGS_DIR="${RUNTIME_ROOT}/logs"
SECRETS_DIR="/etc/davlos/secrets/openclaw"

SOURCE_COMPOSE="${REPO_ROOT}/templates/openclaw/docker-compose.yaml"
SOURCE_ENV="${REPO_ROOT}/templates/openclaw/openclaw.env.example"
SOURCE_CONFIG_EXAMPLE="${REPO_ROOT}/templates/openclaw/openclaw.json.example"
TARGET_COMPOSE="${COMPOSE_DIR}/docker-compose.yaml"
TARGET_ENV="${COMPOSE_DIR}/.env"
TARGET_CONFIG_EXAMPLE="${CONFIG_DIR}/openclaw.json.example"

declare -a CREATED_DIRS=()
declare -a EXISTING_DIRS=()
declare -a COPIED_FILES=()
declare -a SKIPPED_FILES=()
declare -a PENDING_ITEMS=()

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: este script debe ejecutarse con root o sudo." >&2
    exit 1
  fi
}

require_source_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "ERROR: falta la plantilla fuente ${path}" >&2
    exit 1
  fi
}

ensure_dir() {
  local path="$1"

  if [[ -d "${path}" ]]; then
    EXISTING_DIRS+=("${path}")
    return 0
  fi

  if [[ -e "${path}" ]]; then
    echo "ERROR: ${path} existe pero no es un directorio." >&2
    exit 1
  fi

  install -d -m 0750 "${path}"
  CREATED_DIRS+=("${path}")
}

copy_if_missing() {
  local source="$1"
  local target="$2"
  local mode="$3"

  if [[ -e "${target}" ]]; then
    SKIPPED_FILES+=("${target}")
    return 0
  fi

  install -m "${mode}" "${source}" "${target}"
  COPIED_FILES+=("${target}")
}

print_list() {
  local title="$1"
  shift

  echo "${title}"
  if [[ "$#" -eq 0 ]]; then
    echo "- none"
    return 0
  fi

  local item
  for item in "$@"; do
    echo "- ${item}"
  done
}

main() {
  require_root
  require_source_file "${SOURCE_COMPOSE}"
  require_source_file "${SOURCE_ENV}"
  require_source_file "${SOURCE_CONFIG_EXAMPLE}"

  ensure_dir "/opt/automation"
  ensure_dir "/opt/automation/agents"
  ensure_dir "${RUNTIME_ROOT}"
  ensure_dir "${COMPOSE_DIR}"
  ensure_dir "${CONFIG_DIR}"
  ensure_dir "${STATE_DIR}"
  ensure_dir "${LOGS_DIR}"
  ensure_dir "/etc/davlos"
  ensure_dir "/etc/davlos/secrets"
  ensure_dir "${SECRETS_DIR}"

  copy_if_missing "${SOURCE_COMPOSE}" "${TARGET_COMPOSE}" 0640
  copy_if_missing "${SOURCE_ENV}" "${TARGET_ENV}" 0640
  copy_if_missing "${SOURCE_CONFIG_EXAMPLE}" "${TARGET_CONFIG_EXAMPLE}" 0640

  PENDING_ITEMS+=("${TARGET_CONFIG_EXAMPLE} se copia como contrato bootstrap, no como config runtime")
  PENDING_ITEMS+=("${CONFIG_DIR}/openclaw.json no se crea en este tramo")
  PENDING_ITEMS+=("no se crean secretos reales en ${SECRETS_DIR}")
  PENDING_ITEMS+=("no se crea la red Docker agents_net en este tramo")
  PENDING_ITEMS+=("no se arrancan contenedores en este tramo")

  echo "== openclaw runtime staging =="
  echo "repo_root=${REPO_ROOT}"
  echo "runtime_root=${RUNTIME_ROOT}"
  echo "secrets_dir=${SECRETS_DIR}"
  echo

  print_list "-- created directories --" "${CREATED_DIRS[@]}"
  echo
  print_list "-- existing directories --" "${EXISTING_DIRS[@]}"
  echo
  print_list "-- copied files --" "${COPIED_FILES[@]}"
  echo
  print_list "-- skipped existing files --" "${SKIPPED_FILES[@]}"
  echo
  print_list "-- pending items --" "${PENDING_ITEMS[@]}"
}

main "$@"
