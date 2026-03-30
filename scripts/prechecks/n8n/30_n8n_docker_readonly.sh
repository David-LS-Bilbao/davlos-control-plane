#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${1:-root-n8n-1}"
VOLUME_NAME="${2:-root_n8n_data}"
NETWORK_NAME="${3:-verity_network}"

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
