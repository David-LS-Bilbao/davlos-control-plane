#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="/opt/automation/agents/openclaw"
COMPOSE_DIR="${RUNTIME_ROOT}/compose"
CONFIG_DIR="${RUNTIME_ROOT}/config"
STATE_DIR="${RUNTIME_ROOT}/state"
LOGS_DIR="${RUNTIME_ROOT}/logs"
SECRETS_DIR="/etc/davlos/secrets/openclaw"

COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yaml"
ENV_FILE="${COMPOSE_DIR}/.env"
CONFIG_EXAMPLE_FILE="${CONFIG_DIR}/openclaw.json.example"
CONFIG_FILE="${CONFIG_DIR}/openclaw.json"

STATE="NOT_STAGED"
EXIT_CODE=1

status_dir() {
  local path="$1"
  if [[ -d "${path}" ]]; then
    echo "present"
  else
    echo "missing"
  fi
}

status_file() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    echo "present"
  else
    echo "missing"
  fi
}

env_key_status() {
  local key="$1"
  if [[ -f "${ENV_FILE}" ]] && grep -Eq "^${key}=" "${ENV_FILE}"; then
    echo "present"
  else
    echo "missing"
  fi
}

env_key_value() {
  local key="$1"
  if [[ ! -f "${ENV_FILE}" ]]; then
    return 1
  fi
  sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -n 1
}

is_placeholder_image() {
  local value="${1:-}"
  local lower="${value,,}"

  [[ -z "${value}" ]] && return 0
  [[ "${lower}" == *"reviewed_openclaw_image_or_local_build"* ]] && return 0
  [[ "${lower}" == *"placeholder"* ]] && return 0
  [[ "${lower}" == *"pending"* ]] && return 0
  [[ "${lower}" == *"todo"* ]] && return 0
  [[ "${lower}" == *"set a reviewed image"* ]] && return 0
  return 1
}

is_placeholder_gateway_token() {
  local value="${1:-}"
  local lower="${value,,}"

  [[ -z "${value}" ]] && return 0
  [[ "${lower}" == *"set_local_gateway_token"* ]] && return 0
  [[ "${lower}" == *"placeholder"* ]] && return 0
  [[ "${lower}" == *"pending"* ]] && return 0
  [[ "${lower}" == *"todo"* ]] && return 0
  return 1
}

secrets_dir_state() {
  if [[ ! -d "${SECRETS_DIR}" ]]; then
    echo "missing"
    return 0
  fi

  if find "${SECRETS_DIR}" -mindepth 1 -maxdepth 1 | grep -q .; then
    echo "has_entries"
  else
    echo "empty"
  fi
}

main() {
  local compose_dir_status config_dir_status state_dir_status logs_dir_status secrets_dir_status
  local compose_file_status env_file_status
  local compose_project_key_status runtime_root_key_status gateway_port_key_status image_key_status gateway_token_key_status
  local image_value image_status gateway_token_value gateway_token_status
  local config_example_status config_file_status config_file_note
  local missing_count=0
  local incomplete_count=0

  compose_dir_status="$(status_dir "${COMPOSE_DIR}")"
  config_dir_status="$(status_dir "${CONFIG_DIR}")"
  state_dir_status="$(status_dir "${STATE_DIR}")"
  logs_dir_status="$(status_dir "${LOGS_DIR}")"
  secrets_dir_status="$(secrets_dir_state)"

  compose_file_status="$(status_file "${COMPOSE_FILE}")"
  env_file_status="$(status_file "${ENV_FILE}")"

  compose_project_key_status="$(env_key_status "COMPOSE_PROJECT_NAME")"
  runtime_root_key_status="$(env_key_status "OPENCLAW_RUNTIME_ROOT")"
  gateway_port_key_status="$(env_key_status "OPENCLAW_GATEWAY_PORT")"
  image_key_status="$(env_key_status "OPENCLAW_IMAGE")"
  gateway_token_key_status="$(env_key_status "OPENCLAW_GATEWAY_TOKEN")"

  image_value="$(env_key_value "OPENCLAW_IMAGE" || true)"
  if [[ "${image_key_status}" != "present" ]]; then
    image_status="missing_key"
  elif is_placeholder_image "${image_value}"; then
    image_status="placeholder_or_pending"
  else
    image_status="set"
  fi

  gateway_token_value="$(env_key_value "OPENCLAW_GATEWAY_TOKEN" || true)"
  if [[ "${gateway_token_key_status}" != "present" ]]; then
    gateway_token_status="missing_key"
  elif is_placeholder_gateway_token "${gateway_token_value}"; then
    gateway_token_status="placeholder_or_pending"
  else
    gateway_token_status="set"
  fi

  config_example_status="$(status_file "${CONFIG_EXAMPLE_FILE}")"
  if [[ -f "${CONFIG_FILE}" ]]; then
    config_file_status="present"
    config_file_note="config_present"
  elif [[ -f "${CONFIG_EXAMPLE_FILE}" ]]; then
    config_file_status="pending"
    config_file_note="bootstrap_config_present_runtime_config_pending"
  else
    config_file_status="pending"
    config_file_note="bootstrap_config_missing_runtime_config_pending"
  fi

  for item in \
    "${compose_dir_status}" \
    "${config_dir_status}" \
    "${state_dir_status}" \
    "${logs_dir_status}" \
    "${secrets_dir_status}" \
    "${compose_file_status}" \
    "${env_file_status}" \
    "${compose_project_key_status}" \
    "${runtime_root_key_status}" \
    "${gateway_port_key_status}" \
    "${image_key_status}"
  do
    if [[ "${item}" == "missing" ]]; then
      missing_count=$((missing_count + 1))
    fi
  done

  if [[ "${compose_dir_status}" == "missing" ]] && \
     [[ "${config_dir_status}" == "missing" ]] && \
     [[ "${state_dir_status}" == "missing" ]] && \
     [[ "${logs_dir_status}" == "missing" ]] && \
     [[ "${compose_file_status}" == "missing" ]] && \
     [[ "${env_file_status}" == "missing" ]] && \
     [[ "${secrets_dir_status}" == "missing" ]]; then
    STATE="NOT_STAGED"
    EXIT_CODE=1
  elif (( missing_count > 0 )); then
    STATE="STAGED_INCOMPLETE"
    EXIT_CODE=1
  else
    if [[ "${image_status}" != "set" ]]; then
      incomplete_count=$((incomplete_count + 1))
    fi

    if [[ "${config_file_status}" != "present" ]]; then
      incomplete_count=$((incomplete_count + 1))
    fi

    if [[ "${gateway_token_status}" != "set" ]] && [[ "${secrets_dir_status}" != "has_entries" ]]; then
      incomplete_count=$((incomplete_count + 1))
    fi

    if (( incomplete_count > 0 )); then
      STATE="STAGED_READY_FOR_IMAGE_AND_SECRETS"
      EXIT_CODE=0
    else
      STATE="STAGED_READY_FOR_DEPLOY_PRECHECKS"
      EXIT_CODE=0
    fi
  fi

  echo "== openclaw runtime readiness =="
  echo "runtime_root=${RUNTIME_ROOT}"
  echo "secrets_dir=${SECRETS_DIR}"
  echo
  echo "-- directories --"
  echo "compose_dir=${compose_dir_status}"
  echo "config_dir=${config_dir_status}"
  echo "state_dir=${state_dir_status}"
  echo "logs_dir=${logs_dir_status}"
  echo "secrets_dir=${secrets_dir_status}"
  echo
  echo "-- files --"
  echo "compose_file=${compose_file_status}"
  echo "env_file=${env_file_status}"
  echo "config_json_example=${config_example_status}"
  echo "config_json=${config_file_status}"
  echo "config_json_note=${config_file_note}"
  echo
  echo "-- env keys --"
  echo "COMPOSE_PROJECT_NAME=${compose_project_key_status}"
  echo "OPENCLAW_RUNTIME_ROOT=${runtime_root_key_status}"
  echo "OPENCLAW_GATEWAY_PORT=${gateway_port_key_status}"
  echo "OPENCLAW_IMAGE=${image_key_status}"
  echo "OPENCLAW_IMAGE_STATUS=${image_status}"
  echo "OPENCLAW_GATEWAY_TOKEN=${gateway_token_key_status}"
  echo "OPENCLAW_GATEWAY_TOKEN_STATUS=${gateway_token_status}"
  echo
  echo "RUNTIME_STAGE_STATE=${STATE}"

  exit "${EXIT_CODE}"
}

main "$@"
