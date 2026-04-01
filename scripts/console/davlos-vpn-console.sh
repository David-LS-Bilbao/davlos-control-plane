#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECTION="${1:-}"
OPENCLAW_RUNTIME_ROOT="/opt/automation/agents/openclaw"
OPENCLAW_RUNTIME_COMPOSE="${OPENCLAW_RUNTIME_ROOT}/compose/docker-compose.yaml"
OPENCLAW_RUNTIME_LOG_DIR="${OPENCLAW_RUNTIME_ROOT}/logs"
OPENCLAW_SECRETS_ROOT="/etc/davlos/secrets/openclaw"
OPENCLAW_RUNTIME_MODELS_STATE="${OPENCLAW_RUNTIME_ROOT}/state/agents/main/agent/models.json"
INFERENCE_GATEWAY_SERVICE="inference-gateway.service"
INFERENCE_GATEWAY_LOCAL_ENDPOINT="http://127.0.0.1:11440"
INFERENCE_GATEWAY_AGENTS_ENDPOINT="http://172.22.0.1:11440/v1"
OLLAMA_LOCAL_ENDPOINT="http://127.0.0.1:11434"
OPENCLAW_RESTRICTED_OPERATOR_CLI="${REPO_ROOT}/scripts/agents/openclaw/restricted_operator/cli.py"
OPENCLAW_RESTRICTED_OPERATOR_POLICY_REPO="${REPO_ROOT}/templates/openclaw/restricted_operator_policy.json"
OPENCLAW_RESTRICTED_OPERATOR_POLICY_RUNTIME="${OPENCLAW_RUNTIME_ROOT}/broker/restricted_operator_policy.json"
OPENCLAW_OPERATOR_SESSION_ID="${DAVLOS_OPERATOR_ID:-}"

print_header() {
  printf '\n'
  printf '========================================\n'
  printf '        DAVLOS VPN Console MVP          \n'
  printf '========================================\n'
  printf 'repo=%s\n' "${REPO_ROOT}"
  printf 'timestamp=%s\n' "$(date -u +%FT%TZ)"
  printf '\n'
}

pause_if_interactive() {
  if [[ -t 0 ]]; then
    printf '\nPulsa Enter para continuar...'
    read -r _
  fi
}

safe_run() {
  if "$@"; then
    return 0
  fi
  return 1
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

docker_available() {
  docker ps >/dev/null 2>&1
}

find_openclaw_containers() {
  if docker_available; then
    docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | awk 'tolower($0) ~ /openclaw/'
  fi
}

docker_run_readonly() {
  if ! docker_available; then
    return 1
  fi
  docker "$@"
}

openclaw_inference_endpoint() {
  local path
  for path in \
    "${OPENCLAW_RUNTIME_MODELS_STATE}" \
    "${OPENCLAW_RUNTIME_ROOT}/config/openclaw.json"
  do
    if [[ -f "${path}" ]]; then
      sed -n 's/.*"baseUrl":[[:space:]]*"\([^"]*\)".*/\1/p' "${path}" | head -n 1
      return 0
    fi
  done
  return 1
}

openclaw_broker_policy_path() {
  if [[ -r "${OPENCLAW_RESTRICTED_OPERATOR_POLICY_RUNTIME}" ]]; then
    printf '%s\n' "${OPENCLAW_RESTRICTED_OPERATOR_POLICY_RUNTIME}"
    return 0
  fi
  if [[ -r "${OPENCLAW_RESTRICTED_OPERATOR_POLICY_REPO}" ]]; then
    printf '%s\n' "${OPENCLAW_RESTRICTED_OPERATOR_POLICY_REPO}"
    return 0
  fi
  return 1
}

openclaw_broker_cli_available() {
  command -v python3 >/dev/null 2>&1 && [[ -r "${OPENCLAW_RESTRICTED_OPERATOR_CLI}" ]]
}

openclaw_operator_identity() {
  if [[ -n "${OPENCLAW_OPERATOR_SESSION_ID}" ]]; then
    printf '%s\n' "${OPENCLAW_OPERATOR_SESSION_ID}"
    return 0
  fi
  if command -v id >/dev/null 2>&1; then
    id -un 2>/dev/null || printf '%s\n' "${USER:-unknown}"
    return 0
  fi
  printf '%s\n' "${USER:-unknown}"
}

resolve_openclaw_operator_identity() {
  local default_operator operator
  default_operator="$(openclaw_operator_identity)"
  if [[ ! -t 0 ]]; then
    OPENCLAW_OPERATOR_SESSION_ID="${default_operator}"
    printf '%s\n' "${OPENCLAW_OPERATOR_SESSION_ID}"
    return 0
  fi
  operator="$(prompt_with_default 'operator_id' "${default_operator}")"
  if [[ -z "${operator}" ]]; then
    echo "operator_id requerido."
    return 1
  fi
  OPENCLAW_OPERATOR_SESSION_ID="${operator}"
  printf '%s\n' "${OPENCLAW_OPERATOR_SESSION_ID}"
}

run_openclaw_broker_cli() {
  local policy_path
  if ! openclaw_broker_cli_available; then
    echo "CLI del broker no disponible en esta sesión." >&2
    return 1
  fi
  if ! policy_path="$(openclaw_broker_policy_path 2>/dev/null)"; then
    echo "No hay policy del broker visible en esta sesión." >&2
    return 1
  fi
  python3 "${OPENCLAW_RESTRICTED_OPERATOR_CLI}" --policy "${policy_path}" "$@"
}

show_inference_gateway_summary() {
  local active_state="unknown"
  local sub_state="unknown"
  local main_pid="unknown"
  local healthz

  echo "-- inference-gateway host --"
  if command -v systemctl >/dev/null 2>&1; then
    active_state="$(systemctl is-active "${INFERENCE_GATEWAY_SERVICE}" 2>/dev/null || true)"
    sub_state="$(systemctl show -p SubState --value "${INFERENCE_GATEWAY_SERVICE}" 2>/dev/null || true)"
    main_pid="$(systemctl show -p MainPID --value "${INFERENCE_GATEWAY_SERVICE}" 2>/dev/null || true)"
    echo "service=${INFERENCE_GATEWAY_SERVICE}"
    echo "active_state=${active_state:-unknown}"
    echo "sub_state=${sub_state:-unknown}"
    echo "main_pid=${main_pid:-unknown}"
  else
    echo "systemctl_not_available=yes"
  fi

  echo "host_endpoint_local=${INFERENCE_GATEWAY_LOCAL_ENDPOINT}"
  echo "agents_net_endpoint=${INFERENCE_GATEWAY_AGENTS_ENDPOINT}"
  echo "ollama_upstream=${OLLAMA_LOCAL_ENDPOINT}"

  healthz="$(curl -fsS "${INFERENCE_GATEWAY_LOCAL_ENDPOINT}/healthz" 2>/dev/null || true)"
  if [[ -n "${healthz}" ]]; then
    echo "healthz=${healthz}"
  else
    echo "healthz=unavailable_from_this_session"
  fi
}

show_inference_gateway_logs() {
  local journal_output

  echo "-- ${INFERENCE_GATEWAY_SERVICE} --"
  if ! command -v journalctl >/dev/null 2>&1; then
    echo "journalctl no disponible en esta sesión."
    return 0
  fi

  journal_output="$(journalctl -u "${INFERENCE_GATEWAY_SERVICE}" -n 20 --no-pager 2>&1 || true)"
  if [[ -n "$(printf '%s' "${journal_output}" | tr -d '[:space:]')" ]]; then
    printf '%s\n' "${journal_output}" | redact_sensitive_output
  else
    echo "Sin entradas de journal visibles desde esta sesión."
  fi
}

show_host_status() {
  print_header
  echo "[Estado general del host]"
  echo
  echo "-- hostnamectl --"
  if ! safe_run hostnamectl; then
    echo "hostnamectl no disponible; usando uname."
    uname -a
  fi
  echo
  echo "-- uptime --"
  uptime || true
  echo
  echo "-- disk --"
  df -h / /opt 2>/dev/null || df -h / 2>/dev/null || true
}

show_docker_status() {
  print_header
  echo "[Estado de Docker]"
  echo
  if docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' >/tmp/davlos_console_docker_ps.txt 2>/tmp/davlos_console_docker_ps.err; then
    cat /tmp/davlos_console_docker_ps.txt
  else
    echo "Acceso directo a Docker no disponible desde esta sesión."
    if sudo -n /usr/local/sbin/davlos-n8n-audit-readonly docker_readonly >/tmp/davlos_console_docker_readonly.txt 2>/tmp/davlos_console_docker_readonly.err; then
      echo
      echo "Wrapper readonly de host disponible."
      echo "Nota: este wrapper sigue siendo legado y no debe usarse como fuente final si difiere del runtime documentado."
      echo
      sed -n '1,40p' /tmp/davlos_console_docker_readonly.txt
    else
      echo "Tampoco hay wrapper readonly utilizable para Docker/n8n en esta sesión."
      cat /tmp/davlos_console_docker_ps.err 2>/dev/null || true
      cat /tmp/davlos_console_docker_readonly.err 2>/dev/null || true
    fi
  fi
}

show_n8n_status() {
  print_header
  echo "[Estado de n8n]"
  echo
  echo "-- resumen operativo actual --"
  awk '
    /^## Estado de n8n/ {flag=1; next}
    /^## / && flag {exit}
    flag
  ' "${REPO_ROOT}/README.md"
  echo
  echo "-- fase 4 --"
  sed -n '1,120p' "${REPO_ROOT}/evidence/FASE_4_ESTADO.md"
  echo
  echo "-- inventario funcional minimo --"
  sed -n '1,160p' "${REPO_ROOT}/evidence/n8n/N8N_WORKFLOW_MINIMUM_INVENTORY.md"
}

show_network_status() {
  print_header
  echo "[Red / listeners / puertos clave]"
  echo
  echo "-- listeners clave --"
  if ! ss -lntp 2>/dev/null | grep -E ':(22|80|81|443|5678|51820|11434)\b'; then
    echo "No se pudieron listar los puertos clave desde esta sesión."
  fi
}

show_evidence_paths() {
  print_header
  echo "[Ultimas evidencias / ruta de control-plane]"
  echo
  printf 'repo=%s\n' "${REPO_ROOT}"
  echo
  echo "-- rutas clave --"
  printf '%s\n' \
    "${REPO_ROOT}/README.md" \
    "${REPO_ROOT}/evidence/FASE_4_ESTADO.md" \
    "${REPO_ROOT}/evidence/n8n/N8N_WORKFLOW_MINIMUM_INVENTORY.md" \
    "${REPO_ROOT}/evidence/prechecks/n8n/2026-03-31/45_n8n_workflow_inventory_readonly.txt" \
    "${REPO_ROOT}/docs/MVP_PHASE_5_AGENT_ZONE.md" \
    "${REPO_ROOT}/docs/MVP_PHASE_6_INFERENCE_GATEWAY.md" \
    "${REPO_ROOT}/docs/MVP_PHASE_8_RESTRICTED_OPERATOR.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_SECURITY_MVP.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md" \
    "${REPO_ROOT}/runbooks/OPENCLAW_DEPLOY_MVP.md" \
    "${REPO_ROOT}/runbooks/OPENCLAW_ROLLBACK_MVP.md" \
    "${REPO_ROOT}/evidence/agents/OPENCLAW_MVP_VALIDATION_2026-03-31.md"
  echo
  echo "-- ultimos ficheros de evidencia --"
  find "${REPO_ROOT}/evidence" -maxdepth 3 -type f -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort | tail -n 12
}

show_agents_zone() {
  print_header
  echo "[Zona de agentes]"
  echo
  echo "-- objetivo --"
  echo "Zona separada para OpenClaw y futuros agentes, sin tocar verity_network ni servicios existentes."
  echo
  echo "-- estado actual --"
  if [[ -d "${OPENCLAW_RUNTIME_ROOT}" ]]; then
    echo "runtime_root_exists=yes"
  else
    echo "runtime_root_exists=no"
  fi
  if [[ -f "${OPENCLAW_RUNTIME_COMPOSE}" ]]; then
    echo "runtime_compose_exists=yes"
  else
    echo "runtime_compose_exists=no"
  fi
  if [[ -d "${OPENCLAW_SECRETS_ROOT}" ]]; then
    echo "secrets_root_exists=yes"
  else
    echo "secrets_root_exists=no"
  fi
  echo "target_network=agents_net"
  echo "target_gateway_bind=127.0.0.1:18789"
  echo
  echo "-- documentos MVP --"
  printf '%s\n' \
    "${REPO_ROOT}/docs/MVP_PHASE_5_AGENT_ZONE.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_SECURITY_MVP.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md"
}

show_openclaw_status() {
  local openclaw_host_present="no"
  local inference_endpoint="unknown"
  print_header
  echo "[OpenClaw / inference-gateway MVP]"
  echo
  if command -v openclaw >/dev/null 2>&1; then
    openclaw_host_present="yes"
  fi
  echo "-- estado base --"
  echo "openclaw_cli_host_present=${openclaw_host_present}"
  if [[ -d "${OPENCLAW_RUNTIME_ROOT}" ]]; then
    echo "runtime_root=${OPENCLAW_RUNTIME_ROOT}"
  else
    echo "runtime_root=NOT_DEPLOYED"
  fi
  echo "runtime_compose_path=${OPENCLAW_RUNTIME_COMPOSE}"
  if [[ -r "${OPENCLAW_RUNTIME_COMPOSE}" ]]; then
    echo "runtime_compose_readable=yes"
  else
    echo "runtime_compose_readable=no"
  fi
  echo "repo_template=${REPO_ROOT}/templates/openclaw/docker-compose.yaml"
  echo "repo_env_example=${REPO_ROOT}/templates/openclaw/openclaw.env.example"
  if inference_endpoint="$(openclaw_inference_endpoint 2>/dev/null)"; then
    echo "openclaw_inference_endpoint=${inference_endpoint}"
  else
    echo "openclaw_inference_endpoint=unknown"
  fi
  echo
  echo "-- runtime Docker readonly --"
  if docker_available; then
    local found=0
    while IFS= read -r line; do
      found=1
      local cname
      cname="$(printf '%s\n' "${line}" | awk -F '\t' '{print $1}')"
      echo "container=${cname}"
      docker_run_readonly inspect "${cname}" --format 'image={{.Config.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' 2>/dev/null || true
      docker_run_readonly inspect "${cname}" --format 'bind_local={{range $p, $v := .NetworkSettings.Ports}}{{if eq $p "18789/tcp"}}{{range $v}}{{.HostIp}}:{{.HostPort}}{{end}}{{end}}{{end}}' 2>/dev/null || true
      docker_run_readonly inspect "${cname}" --format '{{range $name, $cfg := .NetworkSettings.Networks}}network={{$name}} container_ip={{$cfg.IPAddress}}{{println}}{{end}}' 2>/dev/null || true
      docker_run_readonly inspect "${cname}" --format '{{range .Mounts}}{{if or (eq .Destination "/workspace/config") (eq .Destination "/workspace/state") (eq .Destination "/workspace/logs") (eq .Destination "/run/secrets/openclaw")}}mount={{.Destination}} <= {{.Source}} rw={{.RW}}{{println}}{{end}}{{end}}' 2>/dev/null || true
      docker_run_readonly inspect "${cname}" --format 'security_opt={{json .HostConfig.SecurityOpt}}' 2>/dev/null || true
      docker_run_readonly inspect "${cname}" --format 'cap_drop={{json .HostConfig.CapDrop}}' 2>/dev/null || true
      echo
    done < <(find_openclaw_containers || true)
    if [[ "${found}" -eq 0 ]]; then
      echo "OPENCLAW_RUNTIME_NOT_DETECTED"
    fi
  else
    echo "Acceso directo a Docker no disponible desde esta sesión."
  fi
  echo
  show_inference_gateway_summary
  echo
  echo "-- control basico previsto --"
  echo "status/logs/health: visibles en consola"
  echo "start/stop/restart: no habilitados en este MVP readonly"
}

show_openclaw_logs() {
  print_header
  echo "[OpenClaw / inference-gateway logs]"
  echo
  echo "-- openclaw-gateway --"
  if docker_available; then
    local found=0
    while IFS= read -r line; do
      found=1
      local cname
      cname="$(printf '%s\n' "${line}" | awk -F '\t' '{print $1}')"
      echo "-- ${cname} --"
      if ! docker logs --tail 40 "${cname}" 2>/dev/null | redact_sensitive_output; then
        echo "No se pudieron leer logs de ${cname}."
      fi
      echo
    done < <(find_openclaw_containers || true)
    if [[ "${found}" -eq 0 ]]; then
      echo "OPENCLAW_RUNTIME_NOT_DETECTED"
    fi
    return 0
  fi
  echo "Sin acceso directo a Docker; intento de fallback al runtime local."
  if [[ -d "${OPENCLAW_RUNTIME_LOG_DIR}" ]]; then
    local runtime_logs
    runtime_logs="$(find "${OPENCLAW_RUNTIME_LOG_DIR}" -maxdepth 1 -type f 2>/dev/null | sort | tail -n 5 || true)"
    if [[ -n "${runtime_logs}" ]]; then
      while read -r logfile; do
        echo "-- ${logfile} --"
        tail -n 40 "${logfile}" 2>/dev/null | redact_sensitive_output || true
        echo
      done <<< "${runtime_logs}"
    else
      echo "Sin ficheros de log visibles en ${OPENCLAW_RUNTIME_LOG_DIR}."
    fi
  else
    echo "Sin acceso a Docker y sin directorio de logs desplegado."
  fi
  echo
  show_inference_gateway_logs
}

show_openclaw_health() {
  print_header
  echo "[OpenClaw / inference-gateway health]"
  echo
  echo "-- OpenClaw --"
  if docker_available; then
    local found=0
    while IFS= read -r line; do
      found=1
      local cname
      cname="$(printf '%s\n' "${line}" | awk -F '\t' '{print $1}')"
      echo "container=${cname}"
      docker_run_readonly inspect "${cname}" --format 'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' 2>/dev/null || true
      echo
    done < <(find_openclaw_containers || true)
    if [[ "${found}" -eq 0 ]]; then
      echo "OPENCLAW_RUNTIME_NOT_DETECTED"
    fi
  else
    echo "Acceso directo a Docker no disponible desde esta sesión."
  fi
  echo
  show_inference_gateway_summary
}

show_openclaw_capabilities() {
  print_header
  echo "[OpenClaw / capacidades]"
  echo
  if policy_path="$(openclaw_broker_policy_path 2>/dev/null)"; then
    echo "policy_path=${policy_path}"
  else
    echo "policy_path=unavailable"
  fi
  echo
  if ! openclaw_broker_cli_available; then
    echo "CLI del broker no disponible desde esta sesión."
    return 0
  fi
  cat <<'EOF'
-- lectura del estado efectivo --
- readonly: visible para operador/viewer
- allowed=yes: la acción podría ejecutarse ahora mismo
- restricted: acción mutante o sensible
EOF
  echo
  if ! run_openclaw_broker_cli show --format console; then
    echo
    echo "No se pudo leer el estado efectivo del broker desde esta sesión."
    echo "Posible causa: policy no visible o permisos insuficientes."
  fi
}

show_openclaw_capabilities_audit() {
  print_header
  echo "[OpenClaw / auditoria de capacidades]"
  echo
  if ! openclaw_broker_cli_available; then
    echo "CLI del broker no disponible desde esta sesión."
    return 0
  fi
  echo "-- solo lectura; por Telegram, /audit_tail puede quedar reservado a admin --"
  echo
  if ! run_openclaw_broker_cli audit-tail --lines 20 --format console | redact_sensitive_output; then
    echo "No se pudo leer la auditoria del broker desde esta sesión."
  fi
}

prompt_with_default() {
  local prompt="$1"
  local default_value="$2"
  local value
  printf '%s [%s]: ' "${prompt}" "${default_value}"
  read -r value
  if [[ -z "${value}" ]]; then
    value="${default_value}"
  fi
  printf '%s\n' "${value}"
}

prompt_optional() {
  local prompt="$1"
  local value
  printf '%s: ' "${prompt}"
  read -r value
  printf '%s\n' "${value}"
}

apply_openclaw_capability_change() {
  local subcommand="$1"
  shift
  local cli_output rc=0
  if ! openclaw_broker_cli_available; then
    echo "CLI del broker no disponible desde esta sesión."
    return 1
  fi
  cli_output="$(run_openclaw_broker_cli "$@" 2>&1)" || rc=$?
  if [[ "${rc}" -eq 0 ]]; then
    printf '%s\n' "${cli_output}" | redact_sensitive_output
    return 0
  fi
  printf '%s\n' "${cli_output}" | redact_sensitive_output
  echo
  echo "No se pudo aplicar ${subcommand} desde esta sesión."
  if printf '%s' "${cli_output}" | grep -q 'operator_not_authorized'; then
    echo "Causa probable: el operator_id actual no tiene permiso suficiente para esta accion."
  elif printf '%s' "${cli_output}" | grep -q 'unknown_action'; then
    echo "Causa probable: action_id no reconocido por la policy viva."
  elif printf '%s' "${cli_output}" | grep -q 'invalid datetime'; then
    echo "Causa probable: TTL o fecha de expiracion invalida."
  else
    echo "Causa probable: policy no visible, permisos insuficientes o validacion rechazada."
  fi
  return 1
}

openclaw_capability_enable_flow() {
  local action_id reason operator
  action_id="$(prompt_optional 'action_id')"
  if [[ -z "${action_id}" ]]; then
    echo "action_id requerido."
    return 1
  fi
  operator="$(resolve_openclaw_operator_identity)" || return 1
  reason="$(prompt_with_default 'motivo' 'enabled_from_console')"
  printf 'operator_id=%s\n' "${operator}"
  apply_openclaw_capability_change "enable" enable --action-id "${action_id}" --operator-id "${operator}" --reason "${reason}"
}

openclaw_capability_disable_flow() {
  local action_id reason operator
  action_id="$(prompt_optional 'action_id')"
  if [[ -z "${action_id}" ]]; then
    echo "action_id requerido."
    return 1
  fi
  operator="$(resolve_openclaw_operator_identity)" || return 1
  reason="$(prompt_with_default 'motivo' 'disabled_from_console')"
  printf 'operator_id=%s\n' "${operator}"
  apply_openclaw_capability_change "disable" disable --action-id "${action_id}" --operator-id "${operator}" --reason "${reason}"
}

openclaw_capability_ttl_flow() {
  local action_id ttl_minutes reason operator
  action_id="$(prompt_optional 'action_id')"
  if [[ -z "${action_id}" ]]; then
    echo "action_id requerido."
    return 1
  fi
  ttl_minutes="$(prompt_optional 'ttl_minutes')"
  if [[ -z "${ttl_minutes}" ]]; then
    echo "ttl_minutes requerido."
    return 1
  fi
  operator="$(resolve_openclaw_operator_identity)" || return 1
  reason="$(prompt_with_default 'motivo' 'ttl_enabled_from_console')"
  printf 'operator_id=%s\n' "${operator}"
  apply_openclaw_capability_change "enable-with-ttl" enable --action-id "${action_id}" --ttl-minutes "${ttl_minutes}" --operator-id "${operator}" --reason "${reason}"
}

openclaw_capability_reset_one_shot_flow() {
  local action_id reason operator
  action_id="$(prompt_optional 'action_id')"
  if [[ -z "${action_id}" ]]; then
    echo "action_id requerido."
    return 1
  fi
  operator="$(resolve_openclaw_operator_identity)" || return 1
  reason="$(prompt_with_default 'motivo' 'reset_one_shot_from_console')"
  printf 'operator_id=%s\n' "${operator}"
  apply_openclaw_capability_change "reset-one-shot" reset-one-shot --action-id "${action_id}" --operator-id "${operator}" --reason "${reason}"
}

show_help() {
  print_header
  echo "[Ayuda / limites del MVP]"
  echo
  cat <<'EOF'
- Esta consola es readonly.
- El submenu de capacidades mezcla lectura y mutacion controlada.
- Lectura: ver estado y auditoria.
- Mutacion: enable/disable/ttl/reset-one-shot, siempre via CLI/policy.
- No reinicia servicios, no toca secretos y no modifica producción.
- Si una comprobación requiere Docker o sudo y no está disponible, muestra un aviso y sigue.
- La fuente de verdad operativa actual está en README.md y evidence/.
- El inventario funcional mínimo de workflows de n8n sigue en estado PARTIAL por acceso readonly limitado al runtime activo.
- OpenClaw e inference-gateway se presentan en modo readonly usando Docker/systemd/journal si están disponibles en la sesión.
- El submenu de capacidades OpenClaw usa la CLI del broker; si no hay permisos suficientes o el operador no esta autorizado, degrada con mensaje claro.
- Start/stop/restart quedan fuera de esta consola MVP.
EOF
}

show_menu() {
  print_header
  cat <<'EOF'
1) Estado general del host
2) Estado de Docker
3) Estado de n8n
4) Red / listeners / puertos clave
5) Ultimas evidencias / ruta de control-plane
6) Zona de agentes
7) OpenClaw / inference-gateway
8) Ayuda / limites del MVP
9) Salir
EOF
}

show_agents_menu() {
  print_header
  cat <<'EOF'
[Zona de agentes]
1) Resumen de la zona
2) Seguridad y allowlist
9) Volver
EOF
}

show_openclaw_menu() {
  print_header
  cat <<'EOF'
[OpenClaw / inference-gateway]
1) Estado MVP
2) Logs utiles
3) Health
4) Control basico previsto
5) Capacidades OpenClaw (read + mutate)
9) Volver
EOF
}

show_openclaw_capabilities_menu() {
  print_header
  cat <<'EOF'
[OpenClaw / capacidades]
1) Ver estado efectivo [readonly]
2) Habilitar accion [mutating]
3) Deshabilitar accion [mutating]
4) Habilitar accion con TTL [mutating]
5) Resetear one-shot consumido [mutating]
6) Ver auditoria reciente [readonly]
9) Volver
EOF
}

run_agents_section() {
  case "$1" in
    1|summary) show_agents_zone ;;
    2|security)
      print_header
      printf '%s\n\n' "[Zona de agentes: seguridad y allowlist]"
      sed -n '1,220p' "${REPO_ROOT}/docs/AGENT_ZONE_SECURITY_MVP.md"
      printf '\n'
      sed -n '1,220p' "${REPO_ROOT}/docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md"
      ;;
    9|back) return 1 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 2
      ;;
  esac
}

run_openclaw_section() {
  case "$1" in
    1|status) show_openclaw_status ;;
    2|logs) show_openclaw_logs ;;
    3|health) show_openclaw_health ;;
    4|controls)
      print_header
      printf '%s\n\n' "[OpenClaw / inference-gateway: control basico previsto]"
      cat <<'EOF'
- status: visible en la consola
- logs: visibles en la consola
- health: visible en la consola
- inference-gateway host: visible en la consola
- start/stop/restart: no habilitados en este MVP readonly
- despliegue y rollback: definidos en runbooks del control-plane
EOF
      ;;
    5|capabilities)
      while true; do
        show_openclaw_capabilities_menu
        printf 'Selecciona una opcion: '
        read -r openclaw_cap_choice
        case "${openclaw_cap_choice}" in
          1) show_openclaw_capabilities ;;
          2) openclaw_capability_enable_flow ;;
          3) openclaw_capability_disable_flow ;;
          4) openclaw_capability_ttl_flow ;;
          5) openclaw_capability_reset_one_shot_flow ;;
          6) show_openclaw_capabilities_audit ;;
          9) break ;;
          *)
            echo "Opcion no valida: ${openclaw_cap_choice}" >&2
            ;;
        esac
        pause_if_interactive
      done
      ;;
    9|back) return 1 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 2
      ;;
  esac
}

run_section() {
  case "$1" in
    1|host) show_host_status ;;
    2|docker) show_docker_status ;;
    3|n8n) show_n8n_status ;;
    4|network|ports) show_network_status ;;
    5|evidence) show_evidence_paths ;;
    6|agents) show_agents_zone ;;
    7|openclaw) show_openclaw_status ;;
    openclaw-capabilities) show_openclaw_capabilities ;;
    openclaw-capabilities-audit) show_openclaw_capabilities_audit ;;
    8|help) show_help ;;
    openclaw-logs) show_openclaw_logs ;;
    openclaw-health) show_openclaw_health ;;
    9|exit) exit 0 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 1
      ;;
  esac
}

if [[ -n "${SECTION}" ]]; then
  run_section "${SECTION}"
  exit 0
fi

while true; do
  show_menu
  printf 'Selecciona una opcion: '
  read -r choice
  case "${choice}" in
    6)
      while true; do
        show_agents_menu
        printf 'Selecciona una opcion: '
        read -r agents_choice
        if ! run_agents_section "${agents_choice}"; then
          break
        fi
        pause_if_interactive
      done
      ;;
    7)
      while true; do
        show_openclaw_menu
        printf 'Selecciona una opcion: '
        read -r openclaw_choice
        if ! run_openclaw_section "${openclaw_choice}"; then
          break
        fi
        pause_if_interactive
      done
      ;;
    9)
      echo "Saliendo."
      exit 0
      ;;
    *)
      if run_section "${choice}"; then
        pause_if_interactive
      else
        pause_if_interactive
      fi
      ;;
  esac
done
