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
SOURCE_CONFIG="${REPO_ROOT}/templates/openclaw/openclaw.json.example"
TARGET_COMPOSE="${COMPOSE_DIR}/docker-compose.yaml"
TARGET_ENV="${COMPOSE_DIR}/.env"
TARGET_CONFIG="${CONFIG_DIR}/openclaw.json"
TARGET_CONFIG_EXAMPLE="${CONFIG_DIR}/openclaw.json.example"

DEFAULT_IMAGE="ghcr.io/openclaw/openclaw:2026.2.3"
DEFAULT_PORT="18789"
DEFAULT_GATEWAY_API_KEY="davlos-local"
EXPECTED_AGENTS_SUBNET="172.22.0.0/16"
EXPECTED_AGENTS_GATEWAY="172.22.0.1"

timestamp() {
  date -u +"%Y%m%dT%H%M%SZ"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: este script debe ejecutarse con root o sudo." >&2
    exit 1
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "ERROR: falta el comando requerido: ${cmd}" >&2
    exit 1
  fi
}

ensure_dir() {
  local path="$1"
  local mode="$2"
  local owner="$3"
  local group="$4"

  install -d -m "${mode}" -o "${owner}" -g "${group}" "${path}"
}

backup_if_exists() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    cp -a "${path}" "${path}.bak.$(timestamp)"
  fi
}

copy_with_backup() {
  local source="$1"
  local target="$2"
  local mode="$3"
  local owner="$4"
  local group="$5"

  if [[ -f "${target}" ]] && cmp -s "${source}" "${target}"; then
    return 0
  fi

  backup_if_exists "${target}"
  install -m "${mode}" -o "${owner}" -g "${group}" "${source}" "${target}"
}

set_env_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp

  tmp="$(mktemp)"
  if [[ -f "${file}" ]]; then
    awk -F= -v key="${key}" -v value="${value}" '
      BEGIN { updated = 0 }
      $1 == key { print key "=" value; updated = 1; next }
      { print $0 }
      END { if (!updated) print key "=" value }
    ' "${file}" > "${tmp}"
  else
    printf '%s=%s\n' "${key}" "${value}" > "${tmp}"
  fi
  install -m 0640 -o root -g root "${tmp}" "${file}"
  rm -f "${tmp}"
}

read_env_key() {
  local file="$1"
  local key="$2"

  if [[ ! -f "${file}" ]]; then
    return 1
  fi

  sed -n "s/^${key}=//p" "${file}" | tail -n 1
}

redact_sensitive_output() {
  sed -E \
    -e 's/(OPENCLAW_GATEWAY_TOKEN=)[^[:space:]]+/\1[REDACTED]/g' \
    -e 's/(INFERENCE_GATEWAY_API_KEY=)[^[:space:]]+/\1[REDACTED]/g' \
    -e 's/("token"[[:space:]]*:[[:space:]]*")[^"]+(")/\1[REDACTED]\2/g' \
    -e 's/("apiKey"[[:space:]]*:[[:space:]]*")[^"]+(")/\1[REDACTED]\2/g' \
    -e 's/([Aa]uthorization:?[[:space:]]*Bearer[[:space:]]+)[^[:space:]]+/\1[REDACTED]/g' \
    -e 's/([?&]token=)[^&[:space:]]+/\1[REDACTED]/g'
}

print_container_runtime_summary() {
  local container_name="$1"

  docker inspect "${container_name}" --format 'image={{.Config.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} restart={{.HostConfig.RestartPolicy.Name}}'
  docker inspect "${container_name}" --format '{{json .NetworkSettings.Networks}}'
  docker inspect "${container_name}" --format '{{json .Mounts}}'
  docker inspect "${container_name}" --format '{{json .HostConfig.SecurityOpt}}'
  docker inspect "${container_name}" --format '{{json .HostConfig.CapDrop}}'
}

ensure_runtime_layout() {
  ensure_dir "/opt/automation" 0755 root root
  ensure_dir "/opt/automation/agents" 0755 root root
  ensure_dir "${RUNTIME_ROOT}" 0755 root root
  ensure_dir "${COMPOSE_DIR}" 0750 root root
  ensure_dir "${CONFIG_DIR}" 0755 1000 1000
  ensure_dir "${STATE_DIR}" 0755 1000 1000
  ensure_dir "${LOGS_DIR}" 0755 1000 1000
  ensure_dir "/etc/davlos" 0755 root root
  ensure_dir "/etc/davlos/secrets" 0750 root root
  ensure_dir "${SECRETS_DIR}" 0750 root root
}

prepare_runtime_files() {
  local image="$1"
  local port="$2"
  local gateway_token="$3"
  local gateway_api_key="$4"

  copy_with_backup "${SOURCE_COMPOSE}" "${TARGET_COMPOSE}" 0640 root root
  copy_with_backup "${SOURCE_ENV}" "${TARGET_ENV}" 0640 root root
  copy_with_backup "${SOURCE_CONFIG}" "${TARGET_CONFIG_EXAMPLE}" 0644 1000 1000

  backup_if_exists "${TARGET_CONFIG}"
  install -m 0644 -o 1000 -g 1000 "${SOURCE_CONFIG}" "${TARGET_CONFIG}"

  set_env_key "${TARGET_ENV}" "OPENCLAW_RUNTIME_ROOT" "${RUNTIME_ROOT}"
  set_env_key "${TARGET_ENV}" "COMPOSE_PROJECT_NAME" "openclaw"
  set_env_key "${TARGET_ENV}" "OPENCLAW_GATEWAY_PORT" "${port}"
  set_env_key "${TARGET_ENV}" "OPENCLAW_IMAGE" "${image}"
  set_env_key "${TARGET_ENV}" "OPENCLAW_GATEWAY_TOKEN" "${gateway_token}"
  set_env_key "${TARGET_ENV}" "INFERENCE_GATEWAY_API_KEY" "${gateway_api_key}"

  chown -R 1000:1000 "${CONFIG_DIR}" "${STATE_DIR}" "${LOGS_DIR}"
  chmod 0755 "${CONFIG_DIR}" "${STATE_DIR}" "${LOGS_DIR}"
  find "${CONFIG_DIR}" -maxdepth 1 -type f -exec chmod 0644 {} +
}

ensure_agents_net() {
  local actual_subnet actual_gateway

  if ! docker network inspect agents_net >/dev/null 2>&1; then
    docker network create \
      --driver bridge \
      --subnet "${EXPECTED_AGENTS_SUBNET}" \
      --gateway "${EXPECTED_AGENTS_GATEWAY}" \
      agents_net >/dev/null
    return 0
  fi

  actual_subnet="$(docker network inspect agents_net --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}')"
  actual_gateway="$(docker network inspect agents_net --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}')"

  if [[ "${actual_subnet}" != "${EXPECTED_AGENTS_SUBNET}" ]] || [[ "${actual_gateway}" != "${EXPECTED_AGENTS_GATEWAY}" ]]; then
    echo "ERROR: agents_net ya existe pero no usa ${EXPECTED_AGENTS_SUBNET} / ${EXPECTED_AGENTS_GATEWAY}." >&2
    echo "actual_subnet=${actual_subnet:-unknown}" >&2
    echo "actual_gateway=${actual_gateway:-unknown}" >&2
    exit 1
  fi
}

validate_inference_gateway() {
  curl -fsS "http://172.22.0.1:11440/healthz" >/dev/null
  curl -fsS "http://172.22.0.1:11440/v1/models" >/dev/null
}

wait_for_openclaw() {
  local container_name="openclaw-gateway"
  local attempts=30
  local health status

  while (( attempts > 0 )); do
    status="$(docker inspect "${container_name}" --format '{{.State.Status}}' 2>/dev/null || true)"
    health="$(docker inspect "${container_name}" --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)"

    if [[ "${status}" == "running" ]] && [[ "${health}" == "healthy" ]]; then
      return 0
    fi

    sleep 2
    attempts=$((attempts - 1))
  done

  echo "ERROR: openclaw-gateway no alcanzó estado healthy a tiempo." >&2
  docker ps --filter "name=${container_name}" >&2 || true
  docker logs --tail 100 "${container_name}" 2>/dev/null | redact_sensitive_output >&2 || true
  exit 1
}

print_post_checks() {
  local container_name="openclaw-gateway"
  local port="$1"

  echo
  echo "== post-deploy checks =="
  docker ps --filter "name=${container_name}"
  echo
  docker logs --tail 100 "${container_name}" 2>/dev/null | redact_sensitive_output
  echo
  print_container_runtime_summary "${container_name}"
  echo
  curl -fsS "http://127.0.0.1:${port}/" >/dev/null && echo "host_http_probe=ok"
}

main() {
  local image port gateway_token gateway_api_key

  require_root
  require_cmd docker
  require_cmd openssl
  require_cmd curl

  image="${OPENCLAW_IMAGE:-${DEFAULT_IMAGE}}"
  port="${OPENCLAW_GATEWAY_PORT:-${DEFAULT_PORT}}"
  gateway_api_key="${INFERENCE_GATEWAY_API_KEY:-${DEFAULT_GATEWAY_API_KEY}}"
  gateway_token="${OPENCLAW_GATEWAY_TOKEN:-}"

  if [[ -z "${gateway_token}" ]]; then
    if existing_token="$(read_env_key "${TARGET_ENV}" "OPENCLAW_GATEWAY_TOKEN" 2>/dev/null || true)"; then
      gateway_token="${existing_token}"
    fi
  fi
  if [[ -z "${gateway_token}" ]] || [[ "${gateway_token}" == SET_LOCAL_GATEWAY_TOKEN_BEFORE_DEPLOY* ]]; then
    gateway_token="$(openssl rand -hex 32)"
  fi

  ensure_runtime_layout
  prepare_runtime_files "${image}" "${port}" "${gateway_token}" "${gateway_api_key}"

  bash "${SCRIPT_DIR}/20_validate_runtime_readiness.sh"
  ensure_agents_net
  validate_inference_gateway
  docker pull "${image}"
  docker compose --env-file "${TARGET_ENV}" -f "${TARGET_COMPOSE}" up -d openclaw-gateway
  wait_for_openclaw
  print_post_checks "${port}"
}

main "$@"
