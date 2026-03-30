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

readonly CONTAINER_NAME="root-n8n-1"
readonly VOLUME_NAME="root_n8n_data"
readonly NETWORK_NAME="verity_network"
readonly LOCAL_FILES_PATH="/root/local-files"

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

docker_readonly() {
  print_header "docker_readonly"
  echo

  echo "-- container summary --"
  "${DOCKER_BIN}" inspect "${CONTAINER_NAME}" \
    --format 'Name={{.Name}} Image={{.Config.Image}} Status={{.State.Status}} RestartPolicy={{.HostConfig.RestartPolicy.Name}} StartedAt={{.State.StartedAt}}'
  echo

  echo "-- mounts --"
  "${DOCKER_BIN}" inspect "${CONTAINER_NAME}" \
    --format '{{range .Mounts}}{{println .Type "\t" .Source "\t" .Destination}}{{end}}'
  echo

  echo "-- networks --"
  "${DOCKER_BIN}" inspect "${CONTAINER_NAME}" \
    --format '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
  echo

  echo "-- port bindings --"
  "${DOCKER_BIN}" inspect "${CONTAINER_NAME}" \
    --format '{{json .HostConfig.PortBindings}}'
  echo

  echo "-- env keys only --"
  "${DOCKER_BIN}" inspect "${CONTAINER_NAME}" \
    --format '{{range .Config.Env}}{{println .}}{{end}}' | "${CUT_BIN}" -d= -f1 | "${SORT_BIN}" -u
  echo

  echo "-- volume inspect --"
  "${DOCKER_BIN}" volume inspect "${VOLUME_NAME}"
  echo

  echo "-- network inspect --"
  "${DOCKER_BIN}" network inspect "${NETWORK_NAME}"
}

inventory_minimum() {
  print_header "inventory_minimum"
  echo

  echo "-- probable database backend --"
  "${DOCKER_BIN}" exec "${CONTAINER_NAME}" "${SH_BIN}" -lc 'test -f /home/node/.n8n/database.sqlite && echo SQLITE_PRESENT || echo SQLITE_NOT_FOUND'
  echo

  echo "-- local-files top-level counts --"
  "${SH_BIN}" -lc "test -d '${LOCAL_FILES_PATH}' && '${FIND_BIN}' '${LOCAL_FILES_PATH}' -maxdepth 2 -type f | '${WC_BIN}' -l || echo 0"
  echo

  echo "-- local-files disk usage --"
  "${DU_BIN}" -sh "${LOCAL_FILES_PATH}" || true
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
