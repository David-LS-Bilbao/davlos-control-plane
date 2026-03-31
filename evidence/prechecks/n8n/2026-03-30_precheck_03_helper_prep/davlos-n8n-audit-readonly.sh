#!/usr/bin/env bash
set -euo pipefail

readonly DOCKER_BIN="/usr/bin/docker"
readonly DATE_BIN="/usr/bin/date"
readonly CUT_BIN="/usr/bin/cut"
readonly FIND_BIN="/usr/bin/find"
readonly SORT_BIN="/usr/bin/sort"
readonly DU_BIN="/usr/bin/du"
readonly WC_BIN="/usr/bin/wc"
readonly SH_BIN="/bin/sh"

readonly N8N_IMAGE="docker.n8n.io/n8nio/n8n"
readonly DEFAULT_VOLUME_NAME="root_n8n_data"
readonly NETWORK_NAME="verity_network"
readonly DEFAULT_LOCAL_FILES_PATH="/opt/automation/n8n/local-files"

RESOLVED_CONTAINER_NAME=""
RESOLVED_VOLUME_NAME=""
RESOLVED_LOCAL_FILES_PATH=""

usage() {
  echo "Usage: $0 {docker_readonly|inventory_minimum}" >&2
  exit 64
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: this helper must run as root" >&2
    exit 1
  fi
}

require_deps() {
  for bin in "${DOCKER_BIN}" "${DATE_BIN}" "${CUT_BIN}" "${FIND_BIN}" "${SORT_BIN}" "${DU_BIN}" "${WC_BIN}" "${SH_BIN}"; do
    if [[ ! -x "${bin}" ]]; then
      echo "ERROR: missing required binary: ${bin}" >&2
      exit 1
    fi
  done
}

print_header() {
  local mode="$1"
  echo "== davlos n8n audit readonly =="
  echo "mode=${mode}"
  echo "timestamp=$("${DATE_BIN}" -u +%FT%TZ)"
}

resolve_container_name() {
  local id
  local name
  local networks
  local fallback_name=""
  local -a candidates=()

  if [[ -n "${RESOLVED_CONTAINER_NAME}" ]]; then
    printf '%s\n' "${RESOLVED_CONTAINER_NAME}"
    return 0
  fi

  mapfile -t candidates < <("${DOCKER_BIN}" ps --filter "ancestor=${N8N_IMAGE}" --format '{{.ID}}')

  if [[ "${#candidates[@]}" -eq 0 ]]; then
    echo "ERROR: no running n8n container found for image ${N8N_IMAGE}" >&2
    return 1
  fi

  for id in "${candidates[@]}"; do
    name="$("${DOCKER_BIN}" inspect "${id}" --format '{{.Name}}')"
    name="${name#/}"
    [[ -z "${fallback_name}" ]] && fallback_name="${name}"

    networks="$("${DOCKER_BIN}" inspect "${id}" --format '{{range $k, $v := .NetworkSettings.Networks}}{{printf "%s " $k}}{{end}}')"
    case " ${networks} " in
      *" ${NETWORK_NAME} "*) RESOLVED_CONTAINER_NAME="${name}" ; printf '%s\n' "${RESOLVED_CONTAINER_NAME}" ; return 0 ;;
    esac
  done

  if [[ "${#candidates[@]}" -eq 1 ]]; then
    echo "WARN: using fallback n8n container ${fallback_name}; ${NETWORK_NAME} not detected" >&2
    RESOLVED_CONTAINER_NAME="${fallback_name}"
    printf '%s\n' "${RESOLVED_CONTAINER_NAME}"
    return 0
  fi

  echo "ERROR: could not infer current n8n runtime container on ${NETWORK_NAME}" >&2
  return 1
}

resolve_volume_name() {
  local container_name
  local volume_name

  if [[ -n "${RESOLVED_VOLUME_NAME}" ]]; then
    printf '%s\n' "${RESOLVED_VOLUME_NAME}"
    return 0
  fi

  container_name="$(resolve_container_name)"
  volume_name="$("${DOCKER_BIN}" inspect "${container_name}" --format '{{range .Mounts}}{{if and (eq .Type "volume") (eq .Destination "/home/node/.n8n")}}{{println .Name}}{{end}}{{end}}')"
  volume_name="${volume_name//$'\n'/}"

  if [[ -z "${volume_name}" ]]; then
    RESOLVED_VOLUME_NAME="${DEFAULT_VOLUME_NAME}"
  else
    RESOLVED_VOLUME_NAME="${volume_name}"
  fi

  printf '%s\n' "${RESOLVED_VOLUME_NAME}"
}

resolve_local_files_path() {
  local container_name
  local local_files_path

  if [[ -n "${RESOLVED_LOCAL_FILES_PATH}" ]]; then
    printf '%s\n' "${RESOLVED_LOCAL_FILES_PATH}"
    return 0
  fi

  container_name="$(resolve_container_name)"
  local_files_path="$("${DOCKER_BIN}" inspect "${container_name}" --format '{{range .Mounts}}{{if and (eq .Type "bind") (eq .Destination "/files")}}{{println .Source}}{{end}}{{end}}')"
  local_files_path="${local_files_path//$'\n'/}"

  if [[ -z "${local_files_path}" ]]; then
    RESOLVED_LOCAL_FILES_PATH="${DEFAULT_LOCAL_FILES_PATH}"
  else
    RESOLVED_LOCAL_FILES_PATH="${local_files_path}"
  fi

  printf '%s\n' "${RESOLVED_LOCAL_FILES_PATH}"
}

docker_readonly() {
  local container_name
  local volume_name

  container_name="$(resolve_container_name)"
  volume_name="$(resolve_volume_name)"

  print_header "docker_readonly"
  echo

  echo "-- container summary --"
  "${DOCKER_BIN}" inspect "${container_name}" \
    --format 'Name={{.Name}} Image={{.Config.Image}} Status={{.State.Status}} RestartPolicy={{.HostConfig.RestartPolicy.Name}} StartedAt={{.State.StartedAt}}'
  echo

  echo "-- mounts --"
  "${DOCKER_BIN}" inspect "${container_name}" \
    --format '{{range .Mounts}}{{println .Type "\t" .Source "\t" .Destination}}{{end}}'
  echo

  echo "-- networks --"
  "${DOCKER_BIN}" inspect "${container_name}" \
    --format '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
  echo

  echo "-- port bindings --"
  "${DOCKER_BIN}" inspect "${container_name}" \
    --format '{{json .HostConfig.PortBindings}}'
  echo

  echo "-- env keys only --"
  "${DOCKER_BIN}" inspect "${container_name}" \
    --format '{{range .Config.Env}}{{println .}}{{end}}' | "${CUT_BIN}" -d= -f1 | "${SORT_BIN}" -u
  echo

  echo "-- volume inspect --"
  "${DOCKER_BIN}" volume inspect "${volume_name}"
  echo

  echo "-- network inspect --"
  "${DOCKER_BIN}" network inspect "${NETWORK_NAME}"
}

inventory_minimum() {
  local container_name
  local local_files_path

  container_name="$(resolve_container_name)"
  local_files_path="$(resolve_local_files_path)"

  print_header "inventory_minimum"
  echo

  echo "-- probable database backend --"
  "${DOCKER_BIN}" exec "${container_name}" "${SH_BIN}" -lc 'test -f /home/node/.n8n/database.sqlite && echo SQLITE_PRESENT || echo SQLITE_NOT_FOUND'
  echo

  echo "-- local-files top-level counts --"
  "${SH_BIN}" -lc "test -d '${local_files_path}' && '${FIND_BIN}' '${local_files_path}' -maxdepth 2 -type f | '${WC_BIN}' -l || echo 0"
  echo

  echo "-- local-files disk usage --"
  "${DU_BIN}" -sh "${local_files_path}" || true
  echo

  echo "-- workflow artifact hints from accessible staging docs --"
  "${FIND_BIN}" /opt -type f -name '*.workflow.json' 2>/dev/null | "${SORT_BIN}" || true
  echo

  echo "-- note --"
  echo "This helper does not export workflows, secrets, payloads, or environment values."
}

main() {
  require_root
  require_deps

  if [[ $# -ne 1 ]]; then
    usage
  fi

  case "$1" in
    docker_readonly)
      docker_readonly
      ;;
    inventory_minimum)
      inventory_minimum
      ;;
    *)
      usage
      ;;
  esac
}

main "$@"
