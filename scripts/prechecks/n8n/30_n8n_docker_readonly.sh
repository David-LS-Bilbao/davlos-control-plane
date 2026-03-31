#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${1:-}"
VOLUME_NAME="${2:-}"
NETWORK_NAME="${3:-}"

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
  local preferred_network="${NETWORK_NAME:-verity_network}"
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

derive_volume_name() {
  local container_name="$1"
  local volume_name

  volume_name="$(docker_cmd inspect "${container_name}" --format '{{range .Mounts}}{{if and (eq .Type "volume") (eq .Destination "/home/node/.n8n")}}{{println .Name}}{{end}}{{end}}' | head -n 1)"
  if [[ -n "${volume_name}" ]]; then
    printf '%s\n' "${volume_name}"
    return 0
  fi

  volume_name="$(docker_cmd inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Type "volume"}}{{println .Name}}{{end}}{{end}}' | head -n 1)"
  printf '%s\n' "${volume_name}"
}

derive_network_name() {
  local container_name="$1"
  local network_name

  network_name="$(docker_cmd inspect "${container_name}" --format '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' | grep -x 'verity_network' | head -n 1 || true)"
  if [[ -n "${network_name}" ]]; then
    printf '%s\n' "${network_name}"
    return 0
  fi

  network_name="$(docker_cmd inspect "${container_name}" --format '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' | head -n 1)"
  printf '%s\n' "${network_name}"
}

if [[ -z "${CONTAINER_NAME}" ]]; then
  CONTAINER_NAME="$(detect_container_name)"
fi

if [[ -z "${VOLUME_NAME}" ]]; then
  VOLUME_NAME="$(derive_volume_name "${CONTAINER_NAME}")"
fi

if [[ -z "${NETWORK_NAME}" ]]; then
  NETWORK_NAME="$(derive_network_name "${CONTAINER_NAME}")"
fi

echo "== n8n precheck: docker readonly =="
echo "timestamp=$(date -u +%FT%TZ)"
echo "container=${CONTAINER_NAME}"
echo "volume=${VOLUME_NAME}"
echo "network=${NETWORK_NAME}"
echo

echo "-- container summary --"
docker_cmd inspect "${CONTAINER_NAME}" \
  --format 'Name={{.Name}} Image={{.Config.Image}} Status={{.State.Status}} RestartPolicy={{.HostConfig.RestartPolicy.Name}} StartedAt={{.State.StartedAt}}'
echo

echo "-- mounts --"
docker_cmd inspect "${CONTAINER_NAME}" \
  --format '{{range .Mounts}}{{println .Type "\t" .Source "\t" .Destination}}{{end}}'
echo

echo "-- networks --"
docker_cmd inspect "${CONTAINER_NAME}" \
  --format '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
echo

echo "-- port bindings --"
docker_cmd inspect "${CONTAINER_NAME}" \
  --format '{{json .HostConfig.PortBindings}}'
echo

echo "-- env keys only --"
docker_cmd inspect "${CONTAINER_NAME}" \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | cut -d= -f1 | sort -u
echo

echo "-- volume inspect --"
docker_cmd volume inspect "${VOLUME_NAME}"
echo

echo "-- network inspect --"
docker_cmd network inspect "${NETWORK_NAME}"
