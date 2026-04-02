#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECTION="${1:-}"
OPENCLAW_RUNTIME_ROOT="/opt/automation/agents/openclaw"
OPENCLAW_RUNTIME_COMPOSE="${OPENCLAW_RUNTIME_ROOT}/compose/docker-compose.yaml"
OPENCLAW_RUNTIME_LOG_DIR="${OPENCLAW_RUNTIME_ROOT}/logs"
OPENCLAW_SECRETS_ROOT="/etc/davlos/secrets/openclaw"
OPENCLAW_RUNTIME_MODELS_STATE="${OPENCLAW_RUNTIME_ROOT}/state/agents/main/agent/models.json"
OPENCLAW_BROKER_RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT}/broker"
OPENCLAW_BROKER_RUNTIME_STATE="${OPENCLAW_BROKER_RUNTIME_ROOT}/state/restricted_operator_state.json"
OPENCLAW_BROKER_AUDIT_LOG="${OPENCLAW_BROKER_RUNTIME_ROOT}/audit/restricted_operator.jsonl"
OPENCLAW_TELEGRAM_RUNTIME_STATUS="${OPENCLAW_BROKER_RUNTIME_ROOT}/state/telegram_runtime_status.json"
OPENCLAW_READONLY_HELPER="/usr/local/sbin/davlos-openclaw-readonly"
INFERENCE_GATEWAY_SERVICE="inference-gateway.service"
OPENCLAW_TELEGRAM_SERVICE="openclaw-telegram-bot.service"
INFERENCE_GATEWAY_LOCAL_ENDPOINT="http://127.0.0.1:11440"
INFERENCE_GATEWAY_AGENTS_ENDPOINT="http://172.22.0.1:11440/v1"
OLLAMA_LOCAL_ENDPOINT="http://127.0.0.1:11434"
OPENCLAW_RESTRICTED_OPERATOR_CLI="${REPO_ROOT}/scripts/agents/openclaw/restricted_operator/cli.py"
OPENCLAW_RESTRICTED_OPERATOR_POLICY_REPO="${REPO_ROOT}/templates/openclaw/restricted_operator_policy.json"
OPENCLAW_RESTRICTED_OPERATOR_POLICY_RUNTIME="${OPENCLAW_RUNTIME_ROOT}/broker/restricted_operator_policy.json"
OPENCLAW_OPERATOR_SESSION_ID="${DAVLOS_OPERATOR_ID:-}"

COLOR_RESET=""
COLOR_DIM=""
COLOR_BOLD=""
COLOR_BLUE=""
COLOR_CYAN=""
COLOR_GREEN=""
COLOR_YELLOW=""
COLOR_RED=""
COLOR_MAGENTA=""
COLOR_WHITE=""

init_console_style() {
  if [[ -t 1 && "${TERM:-dumb}" != "dumb" ]]; then
    COLOR_RESET=$'\033[0m'
    COLOR_DIM=$'\033[2m'
    COLOR_BOLD=$'\033[1m'
    COLOR_BLUE=$'\033[34m'
    COLOR_CYAN=$'\033[36m'
    COLOR_GREEN=$'\033[32m'
    COLOR_YELLOW=$'\033[33m'
    COLOR_RED=$'\033[31m'
    COLOR_MAGENTA=$'\033[35m'
    COLOR_WHITE=$'\033[37m'
  fi
}

style_text() {
  local style="$1"
  local text="$2"
  printf '%b%s%b' "${style}" "${text}" "${COLOR_RESET}"
}

badge() {
  local kind="$1"
  local label="$2"
  local color="${COLOR_WHITE}"
  case "${kind}" in
    readonly) color="${COLOR_CYAN}" ;;
    mutating) color="${COLOR_MAGENTA}" ;;
    success) color="${COLOR_GREEN}" ;;
    warning) color="${COLOR_YELLOW}" ;;
    error) color="${COLOR_RED}" ;;
    info) color="${COLOR_BLUE}" ;;
  esac
  printf '%b[%s]%b' "${COLOR_BOLD}${color}" "${label}" "${COLOR_RESET}"
}

rule() {
  printf '%s\n' '================================================================'
}

subrule() {
  printf '%s\n' '----------------------------------------------------------------'
}

panel_text_length() {
  local text="$1"
  printf '%s' "${#text}"
}

panel_truncate_text() {
  local text="$1"
  local max_width="$2"
  if (( max_width <= 0 )); then
    printf '%s' ""
    return
  fi
  if (( ${#text} <= max_width )); then
    printf '%s' "${text}"
    return
  fi
  if (( max_width <= 3 )); then
    printf '%.*s' "${max_width}" "${text}"
    return
  fi
  printf '%.*s...' "$((max_width - 3))" "${text}"
}

panel_row() {
  local left_plain="$1"
  local right_plain="$2"
  local total_width="$3"
  local left_style="${4:-}"
  local right_style="${5:-}"
  local frame_style="${COLOR_BOLD}${COLOR_GREEN}"
  local content_width left_len right_len padding max_left
  local left_rendered right_rendered

  content_width=$((total_width - 4))
  right_len="$(panel_text_length "${right_plain}")"
  if (( right_len > content_width - 1 )); then
    right_plain="$(panel_truncate_text "${right_plain}" "$((content_width - 1))")"
    right_len="$(panel_text_length "${right_plain}")"
  fi

  left_len="$(panel_text_length "${left_plain}")"
  if (( left_len + right_len > content_width )); then
    max_left=$((content_width - right_len - 1))
    if (( max_left < 1 )); then
      max_left=1
    fi
    left_plain="$(panel_truncate_text "${left_plain}" "${max_left}")"
    left_len="$(panel_text_length "${left_plain}")"
  fi

  padding=$((content_width - left_len - right_len))
  if (( padding < 1 )); then
    padding=1
  fi

  left_rendered="${left_plain}"
  if [[ -n "${left_style}" ]]; then
    left_rendered="${left_style}${left_plain}${COLOR_RESET}"
  fi

  right_rendered="${right_plain}"
  if [[ -n "${right_style}" ]]; then
    right_rendered="${right_style}${right_plain}${COLOR_RESET}"
  fi

  printf '%b║%b %s%*s%s %b║%b\n' "${frame_style}" "${COLOR_RESET}" "${left_rendered}" "${padding}" "" "${right_rendered}" "${frame_style}" "${COLOR_RESET}"
}

panel_center_line() {
  local text_plain="$1"
  local total_width="$2"
  local text_style="${3:-}"
  local frame_style="${COLOR_BOLD}${COLOR_GREEN}"
  local content_width text_len left_pad right_pad
  local rendered_text

  content_width=$((total_width - 4))
  text_len="$(panel_text_length "${text_plain}")"
  if (( text_len > content_width )); then
    text_plain="$(panel_truncate_text "${text_plain}" "${content_width}")"
    text_len="$(panel_text_length "${text_plain}")"
  fi

  left_pad=$(((content_width - text_len) / 2))
  right_pad=$((content_width - text_len - left_pad))
  rendered_text="${text_plain}"
  if [[ -n "${text_style}" ]]; then
    rendered_text="${text_style}${text_plain}${COLOR_RESET}"
  fi

  printf '%b║%b %*s%s%*s %b║%b\n' "${frame_style}" "${COLOR_RESET}" "${left_pad}" "" "${rendered_text}" "${right_pad}" "" "${frame_style}" "${COLOR_RESET}"
}

panel_rule() {
  local left_border="$1"
  local fill_char="$2"
  local right_border="$3"
  local total_width="$4"
  local frame_style="${COLOR_BOLD}${COLOR_GREEN}"
  local fill

  printf -v fill '%*s' "$((total_width - 2))" ''
  fill="${fill// /${fill_char}}"
  printf '%b%s%s%s%b\n' "${frame_style}" "${left_border}" "${fill}" "${right_border}" "${COLOR_RESET}"
}

panel_metric_cpu() {
  local metric
  metric="$(LC_ALL=C top -bn1 2>/dev/null | awk -F'[ ,]+' '/^%Cpu\\(s\\):/ {for (i = 1; i <= NF; i++) if ($i == "id") {printf "CPU: %.0f%%", 100 - $(i - 1); found = 1; exit}} END {if (!found) printf "CPU: N/A"}')"
  if [[ -z "${metric}" || "${metric}" == "CPU: N/A" ]]; then
    metric="$(awk '/^cpu / {idle = $5 + $6; total = 0; for (i = 2; i <= NF; i++) total += $i; if (total > 0) {printf "CPU: %.0f%%", ((total - idle) / total) * 100; found = 1; exit}} END {if (!found) printf "CPU: N/A"}' /proc/stat 2>/dev/null)"
  fi
  if [[ -z "${metric}" ]]; then
    metric="CPU: N/A"
  fi
  printf '%s' "${metric}"
}

panel_metric_ram() {
  local metric
  metric="$(free -m 2>/dev/null | awk '/^Mem:/ && $2 > 0 {printf "RAM: %.0f%%", ($3 / $2) * 100; found = 1} END {if (!found) printf "RAM: N/A"}')"
  if [[ -z "${metric}" ]]; then
    metric="RAM: N/A"
  fi
  printf '%s' "${metric}"
}

panel_metric_vpn_nodes() {
  printf '%s' "Nodos VPN: 3 Activos"
}

panel_terminal_width() {
  local width="${COLUMNS:-}"
  if [[ -z "${width}" && -n "${TERM:-}" ]] && command -v tput >/dev/null 2>&1; then
    width="$(tput cols 2>/dev/null || true)"
  fi
  if ! [[ "${width}" =~ ^[0-9]+$ ]]; then
    width=80
  fi
  printf '%s' "${width}"
}

brand_block() {
  local panel_total_width=70
  local terminal_width
  local madrid_time cpu_metric ram_metric vpn_metric combined_metric
  local banner_lines=(
    "██████╗  █████╗ ██╗   ██╗██╗      ██████╗ ███████╗"
    "██╔══██╗██╔══██╗██║   ██║██║     ██╔═══██╗██╔════╝"
    "██║  ██║███████║██║   ██║██║     ██║   ██║███████╗"
    "██║  ██║██╔══██║╚██╗ ██╔╝██║     ██║   ██║╚════██║"
    "██████╔╝██║  ██║ ╚████╔╝ ███████╗╚██████╔╝███████║"
    "╚═════╝ ╚═╝  ╚═╝  ╚═══╝  ╚══════╝ ╚═════╝ ╚══════╝"
  )
  local banner_line

  terminal_width="$(panel_terminal_width)"
  madrid_time="$(TZ="Europe/Madrid" date +%FT%T%z)"
  cpu_metric="$(panel_metric_cpu)"
  ram_metric="$(panel_metric_ram)"
  vpn_metric="$(panel_metric_vpn_nodes)"
  combined_metric="${cpu_metric} | ${ram_metric}"

  if (( terminal_width < 72 )); then
    printf '%b%s%b %b%s%b\n' "${COLOR_BOLD}${COLOR_WHITE}" "DAVLOS VPN Console MVP" "${COLOR_RESET}" "${COLOR_BOLD}${COLOR_GREEN}" "[ ONLINE ]" "${COLOR_RESET}"
    printf '  Repo: %s\n' "${REPO_ROOT}"
    printf '  Hora: %s\n' "${madrid_time}"
    printf '  %s | %s\n' "${cpu_metric}" "${ram_metric}"
    printf '  %s\n' "${vpn_metric}"
    return
  fi

  panel_rule "╔" "═" "╗" "${panel_total_width}"
  for banner_line in "${banner_lines[@]}"; do
    panel_center_line "${banner_line}" "${panel_total_width}" "${COLOR_BOLD}${COLOR_WHITE}"
  done
  panel_rule "╠" "═" "╣" "${panel_total_width}"
  panel_row "VPN Console MVP" "[ ONLINE ]" "${panel_total_width}" "" "${COLOR_BOLD}${COLOR_GREEN}"
  panel_row "Repo: ${REPO_ROOT}" "${combined_metric}" "${panel_total_width}"
  panel_row "Time: ${madrid_time}" "${vpn_metric}" "${panel_total_width}"
  panel_rule "╚" "═" "╝" "${panel_total_width}"
}

print_section_title() {
  printf '%b%s%b\n' "${COLOR_BOLD}${COLOR_WHITE}" "$1" "${COLOR_RESET}"
}

print_subsection() {
  printf '%b%s%b\n' "${COLOR_DIM}${COLOR_CYAN}" "-- $1 --" "${COLOR_RESET}"
}

kv_line() {
  local key="$1"
  local value="$2"
  printf '  %-24s %s\n' "${key}" "${value}"
}

menu_line() {
  local id="$1"
  local label="$2"
  local marker="${3:-}"
  if [[ -n "${marker}" ]]; then
    printf ' %s %-2s %s\n' "$(style_text "${COLOR_BOLD}${COLOR_BLUE}" "${id})")" "" "${label} ${marker}"
  else
    printf ' %s %-2s %s\n' "$(style_text "${COLOR_BOLD}${COLOR_BLUE}" "${id})")" "" "${label}"
  fi
}

notice_line() {
  local kind="$1"
  shift
  printf '%s %s\n' "$(badge "${kind}" "$(printf '%s' "${kind}" | tr '[:lower:]' '[:upper:]')")" "$*"
}

print_header() {
  if [[ -t 1 && -n "${TERM:-}" && "${TERM}" != "dumb" ]]; then
      clear
  fi
  printf '\n'
  brand_block

  local current_user
  current_user="$(whoami)"
  if [[ "${current_user}" != "devops" && "${current_user}" != "root" ]]; then
      printf '\n'
      notice_line warning "Ejecutando como '${current_user}'. Los datos reales requieren lanzar esto como 'devops'."
  fi
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

openclaw_broker_policy_source() {
  if [[ -r "${OPENCLAW_RESTRICTED_OPERATOR_POLICY_RUNTIME}" ]]; then
    printf '%s\n' "runtime"
    return 0
  fi
  if [[ -r "${OPENCLAW_RESTRICTED_OPERATOR_POLICY_REPO}" ]]; then
    printf '%s\n' "repo_fallback"
    return 0
  fi
  printf '%s\n' "unavailable"
}

openclaw_runtime_summary_field() {
  local field="$1"
  local helper_output
  if ! openclaw_readonly_helper_available; then
    return 1
  fi
  helper_output="$(run_openclaw_readonly_helper runtime_summary 2>/dev/null || true)"
  printf '%s\n' "${helper_output}" | sed -n "s/^${field}=//p" | head -n 1
}

openclaw_policy_source_display() {
  local value
  value="$(openclaw_runtime_summary_field policy_source 2>/dev/null || true)"
  if [[ -n "${value}" ]]; then
    printf '%s\n' "${value}"
    return 0
  fi
  openclaw_broker_policy_source
}

openclaw_policy_path_display() {
  local value
  value="$(openclaw_runtime_summary_field policy_path 2>/dev/null || true)"
  if [[ -n "${value}" ]]; then
    printf '%s\n' "${value}"
    return 0
  fi
  openclaw_broker_policy_path 2>/dev/null || printf '%s\n' "unavailable"
}

openclaw_broker_cli_available() {
  command -v python3 >/dev/null 2>&1 && [[ -r "${OPENCLAW_RESTRICTED_OPERATOR_CLI}" ]]
}

openclaw_readonly_helper_available() {
  [[ -f "${OPENCLAW_READONLY_HELPER}" ]] && sudo -n "${OPENCLAW_READONLY_HELPER}" runtime_summary >/dev/null 2>&1
}

run_openclaw_readonly_helper() {
  if ! [[ -f "${OPENCLAW_READONLY_HELPER}" ]]; then
    echo "Helper readonly de OpenClaw no instalado en el host." >&2
    return 1
  fi
  sudo -n "${OPENCLAW_READONLY_HELPER}" "$@"
}

runtime_access_badge() {
  local path="$1"
  if [[ -r "${path}" ]]; then
    printf '%s %s\n' "$(badge success yes)" "direct"
  elif openclaw_readonly_helper_available; then
    printf '%s %s\n' "$(badge success yes)" "via_helper"
  else
    printf '%s %s\n' "$(badge warning no)" "unavailable"
  fi
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

service_active_state() {
  local service="$1"
  if ! command -v systemctl >/dev/null 2>&1; then
    printf '%s\n' "unknown"
    return 0
  fi
  systemctl is-active "${service}" 2>/dev/null || true
}

service_sub_state() {
  local service="$1"
  if ! command -v systemctl >/dev/null 2>&1; then
    printf '%s\n' "unknown"
    return 0
  fi
  systemctl show -p SubState --value "${service}" 2>/dev/null || true
}

service_main_pid() {
  local service="$1"
  if ! command -v systemctl >/dev/null 2>&1; then
    printf '%s\n' "unknown"
    return 0
  fi
  systemctl show -p MainPID --value "${service}" 2>/dev/null || true
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

  print_subsection "inference-gateway host"
  if command -v systemctl >/dev/null 2>&1; then
    active_state="$(systemctl is-active "${INFERENCE_GATEWAY_SERVICE}" 2>/dev/null || true)"
    sub_state="$(systemctl show -p SubState --value "${INFERENCE_GATEWAY_SERVICE}" 2>/dev/null || true)"
    main_pid="$(systemctl show -p MainPID --value "${INFERENCE_GATEWAY_SERVICE}" 2>/dev/null || true)"
    kv_line "service" "${INFERENCE_GATEWAY_SERVICE}"
    kv_line "active_state" "${active_state:-unknown}"
    kv_line "sub_state" "${sub_state:-unknown}"
    kv_line "main_pid" "${main_pid:-unknown}"
  else
    kv_line "systemctl_not_available" "$(badge warning yes)"
  fi

  kv_line "host_endpoint_local" "${INFERENCE_GATEWAY_LOCAL_ENDPOINT}"
  kv_line "agents_net_endpoint" "${INFERENCE_GATEWAY_AGENTS_ENDPOINT}"
  kv_line "ollama_upstream" "${OLLAMA_LOCAL_ENDPOINT}"

  healthz="$(curl -fsS "${INFERENCE_GATEWAY_LOCAL_ENDPOINT}/healthz" 2>/dev/null || true)"
  if [[ -n "${healthz}" ]]; then
    kv_line "healthz" "${healthz}"
  else
    kv_line "healthz" "$(badge warning unavailable_from_this_session)"
  fi
}

show_inference_gateway_logs() {
  local journal_output

  print_subsection "${INFERENCE_GATEWAY_SERVICE}"
  if ! command -v journalctl >/dev/null 2>&1; then
    notice_line warning "journalctl no disponible en esta sesion."
    return 0
  fi

  journal_output="$(journalctl -u "${INFERENCE_GATEWAY_SERVICE}" -n 20 --no-pager 2>&1 || true)"
  if [[ -n "$(printf '%s' "${journal_output}" | tr -d '[:space:]')" ]]; then
    printf '%s\n' "${journal_output}" | redact_sensitive_output
  else
    notice_line warning "Sin entradas de journal visibles desde esta sesion."
  fi
}

show_host_status() {
  print_header
  print_section_title "Estado general del host"
  echo
  print_subsection "identidad del host"
  if ! safe_run hostnamectl; then
    notice_line warning "hostnamectl no disponible; usando uname."
    uname -a
  fi
  echo
  print_subsection "uptime"
  uptime || true
  echo
  print_subsection "disco"
  df -h / /opt 2>/dev/null || df -h / 2>/dev/null || true
}

show_docker_status() {
  print_header
  print_section_title "Estado de Docker"
  echo
  if docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' >/tmp/davlos_console_docker_ps.txt 2>/tmp/davlos_console_docker_ps.err; then
    cat /tmp/davlos_console_docker_ps.txt
  else
    notice_line warning "Acceso directo a Docker no disponible desde esta sesion."
    if sudo -n /usr/local/sbin/davlos-n8n-audit-readonly docker_readonly >/tmp/davlos_console_docker_readonly.txt 2>/tmp/davlos_console_docker_readonly.err; then
      echo
      notice_line readonly "Wrapper readonly de host disponible."
      notice_line warning "Sigue siendo legado; no usarlo como fuente final si difiere del runtime documentado."
      echo
      sed -n '1,40p' /tmp/davlos_console_docker_readonly.txt
    else
      notice_line error "Tampoco hay wrapper readonly utilizable para Docker/n8n en esta sesion."
      cat /tmp/davlos_console_docker_ps.err 2>/dev/null || true
      cat /tmp/davlos_console_docker_readonly.err 2>/dev/null || true
    fi
  fi
}

show_n8n_status() {
  print_header
  print_section_title "Estado de n8n"
  echo
  print_subsection "resumen operativo actual"
  awk '
    /^## Estado de n8n/ {flag=1; next}
    /^## / && flag {exit}
    flag
  ' "${REPO_ROOT}/README.md"
  echo
  print_subsection "fase 4"
  sed -n '1,120p' "${REPO_ROOT}/evidence/FASE_4_ESTADO.md"
  echo
  print_subsection "inventario funcional minimo"
  sed -n '1,160p' "${REPO_ROOT}/evidence/n8n/N8N_WORKFLOW_MINIMUM_INVENTORY.md"
}

show_network_status() {
  print_header
  print_section_title "Red / listeners / puertos clave"
  echo
  print_subsection "listeners clave"
  if ! ss -lntp 2>/dev/null | grep -E ':(22|80|81|443|5678|51820|11434|11440)\b'; then
    notice_line warning "No se pudieron listar los puertos clave desde esta sesion."
  fi
}

show_evidence_paths() {
  print_header
  print_section_title "Ultimas evidencias / ruta de control-plane"
  echo
  kv_line "repo" "${REPO_ROOT}"
  echo
  print_subsection "rutas clave"
  printf '%s\n' \
    "${REPO_ROOT}/README.md" \
    "${REPO_ROOT}/evidence/FASE_4_ESTADO.md" \
    "${REPO_ROOT}/evidence/n8n/N8N_WORKFLOW_MINIMUM_INVENTORY.md" \
    "${REPO_ROOT}/evidence/prechecks/n8n/2026-03-31/45_n8n_workflow_inventory_readonly.txt" \
    "${REPO_ROOT}/docs/MVP_PHASE_5_AGENT_ZONE.md" \
    "${REPO_ROOT}/docs/MVP_PHASE_6_INFERENCE_GATEWAY.md" \
    "${REPO_ROOT}/docs/MVP_PHASE_8_RESTRICTED_OPERATOR.md" \
    "${REPO_ROOT}/docs/TELEGRAM_OPENCLAW_MVP.md" \
    "${REPO_ROOT}/docs/TELEGRAM_OPENCLAW_RUNTIME_MVP.md" \
    "${REPO_ROOT}/docs/OPENCLAW_OPERATOR_FLOWS_MVP.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_SECURITY_MVP.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md" \
    "${REPO_ROOT}/runbooks/OPENCLAW_DEPLOY_MVP.md" \
    "${REPO_ROOT}/runbooks/OPENCLAW_ROLLBACK_MVP.md" \
    "${REPO_ROOT}/evidence/agents/OPENCLAW_MVP_VALIDATION_2026-03-31.md" \
    "${REPO_ROOT}/docs/reports/OPENCLAW_SECURITY_REGRESSION_FIX_2026-04-01.md" \
    "${REPO_ROOT}/docs/reports/OPENCLAW_PHASE_8_HARDENING_MVP_2026-04-01.md" \
    "${REPO_ROOT}/docs/reports/OPENCLAW_PHASE_9_TIMEBOXED_HARDENING_2026-04-01.md" \
    "${REPO_ROOT}/docs/reports/OPENCLAW_PHASE_10_CONSOLE_POLISH_2026-04-01.md" \
    "${REPO_ROOT}/docs/reports/OPENCLAW_PHASE_11_OPERATOR_FLOWS_2026-04-01.md"
  echo
  print_subsection "ultimos ficheros de evidencia"
  find "${REPO_ROOT}/evidence" -maxdepth 3 -type f -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort | tail -n 12
}

show_agents_zone() {
  print_header
  print_section_title "Zona de agentes"
  echo
  print_subsection "objetivo"
  echo "Zona separada para OpenClaw y futuros agentes, sin tocar verity_network ni servicios existentes."
  echo
  print_subsection "estado actual"
  if [[ -d "${OPENCLAW_RUNTIME_ROOT}" ]]; then
    kv_line "runtime_root_exists" "$(badge success yes)"
  else
    kv_line "runtime_root_exists" "$(badge error no)"
  fi
  if [[ -f "${OPENCLAW_RUNTIME_COMPOSE}" ]]; then
    kv_line "runtime_compose_exists" "$(badge success yes)"
  else
    kv_line "runtime_compose_exists" "$(badge error no)"
  fi
  if [[ -d "${OPENCLAW_SECRETS_ROOT}" ]]; then
    kv_line "secrets_root_exists" "$(badge success yes)"
  else
    kv_line "secrets_root_exists" "$(badge error no)"
  fi
  kv_line "target_network" "agents_net"
  kv_line "target_gateway_bind" "127.0.0.1:18789"
  echo
  print_subsection "documentos MVP"
  printf '%s\n' \
    "${REPO_ROOT}/docs/MVP_PHASE_5_AGENT_ZONE.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_SECURITY_MVP.md" \
    "${REPO_ROOT}/docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md"
}

show_openclaw_status() {
  local openclaw_host_present="no"
  local inference_endpoint="unknown"
  print_header
  print_section_title "OpenClaw / inference-gateway MVP"
  echo
  if command -v openclaw >/dev/null 2>&1; then
    openclaw_host_present="yes"
  fi
  print_subsection "estado base"
  kv_line "openclaw_cli_host_present" "${openclaw_host_present}"
  if [[ -d "${OPENCLAW_RUNTIME_ROOT}" ]]; then
    kv_line "runtime_root" "${OPENCLAW_RUNTIME_ROOT}"
  else
    kv_line "runtime_root" "$(badge warning NOT_DEPLOYED)"
  fi
  kv_line "runtime_compose_path" "${OPENCLAW_RUNTIME_COMPOSE}"
  if [[ -r "${OPENCLAW_RUNTIME_COMPOSE}" ]]; then
    kv_line "runtime_compose_readable" "$(badge success yes)"
  else
    kv_line "runtime_compose_readable" "$(badge error no)"
  fi
  kv_line "repo_template" "${REPO_ROOT}/templates/openclaw/docker-compose.yaml"
  kv_line "repo_env_example" "${REPO_ROOT}/templates/openclaw/openclaw.env.example"
  if inference_endpoint="$(openclaw_inference_endpoint 2>/dev/null)"; then
    kv_line "openclaw_inference_endpoint" "${inference_endpoint}"
  else
    kv_line "openclaw_inference_endpoint" "$(badge warning unknown)"
  fi
  echo
  print_subsection "runtime Docker readonly"
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
      notice_line warning "OPENCLAW_RUNTIME_NOT_DETECTED"
    fi
  else
    notice_line warning "Acceso directo a Docker no disponible desde esta sesion."
  fi
  echo
  show_inference_gateway_summary
  echo
  show_openclaw_telegram_summary
  echo
  print_subsection "control basico previsto"
  notice_line readonly "status/logs/health visibles en consola"
  notice_line info "Telegram runtime visible en una vista dedicada cuando systemd y el runtime lo permiten"
  notice_line warning "start/stop/restart no habilitados en esta consola MVP"
}

show_openclaw_logs() {
  print_header
  print_section_title "OpenClaw / inference-gateway logs"
  echo
  print_subsection "openclaw-gateway"
  if docker_available; then
    local found=0
    while IFS= read -r line; do
      found=1
      local cname
      cname="$(printf '%s\n' "${line}" | awk -F '\t' '{print $1}')"
      echo "-- ${cname} --"
      if ! docker logs --tail 40 "${cname}" 2>/dev/null | redact_sensitive_output; then
        notice_line warning "No se pudieron leer logs de ${cname}."
      fi
      echo
    done < <(find_openclaw_containers || true)
    if [[ "${found}" -eq 0 ]]; then
      notice_line warning "OPENCLAW_RUNTIME_NOT_DETECTED"
    fi
    return 0
  fi
  notice_line warning "Sin acceso directo a Docker; intento de fallback al runtime local."
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
      notice_line warning "Sin ficheros de log visibles en ${OPENCLAW_RUNTIME_LOG_DIR}."
    fi
  else
    notice_line error "Sin acceso a Docker y sin directorio de logs desplegado."
  fi
  echo
  show_inference_gateway_logs
}

show_openclaw_health() {
  print_header
  print_section_title "OpenClaw / inference-gateway health"
  echo
  print_subsection "OpenClaw"
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
      notice_line warning "OPENCLAW_RUNTIME_NOT_DETECTED"
    fi
  else
    notice_line warning "Acceso directo a Docker no disponible desde esta sesion."
  fi
  echo
  show_inference_gateway_summary
}

show_openclaw_telegram_summary() {
  local active_state="unknown"
  local sub_state="unknown"
  local main_pid="unknown"

  print_subsection "telegram runtime"
  if command -v systemctl >/dev/null 2>&1; then
    active_state="$(systemctl is-active "${OPENCLAW_TELEGRAM_SERVICE}" 2>/dev/null || true)"
    sub_state="$(systemctl show -p SubState --value "${OPENCLAW_TELEGRAM_SERVICE}" 2>/dev/null || true)"
    main_pid="$(systemctl show -p MainPID --value "${OPENCLAW_TELEGRAM_SERVICE}" 2>/dev/null || true)"
    kv_line "service" "${OPENCLAW_TELEGRAM_SERVICE}"
    kv_line "active_state" "${active_state:-unknown}"
    kv_line "sub_state" "${sub_state:-unknown}"
    kv_line "main_pid" "${main_pid:-unknown}"
  else
    kv_line "systemctl_not_available" "$(badge warning yes)"
  fi
  kv_line "runtime_status_path" "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}"
  kv_line "runtime_status_access" "$(runtime_access_badge "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}")"
  if [[ ! -r "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}" ]] && ! openclaw_readonly_helper_available; then
    notice_line warning "telegram_runtime_status.json no visible desde esta sesion ni via helper readonly."
  fi
  kv_line "commands" "/status /capabilities /audit_tail /execute"
}

show_openclaw_telegram_runtime() {
  local helper_output
  print_header
  print_section_title "OpenClaw / Telegram runtime"
  echo
  show_openclaw_telegram_summary
  if [[ -r "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}" ]]; then
    echo
    print_subsection "ultimo estado runtime"
    sed -n '1,160p' "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}" | redact_sensitive_output
  elif helper_output="$(run_openclaw_readonly_helper telegram_runtime_status 2>/dev/null)"; then
    echo
    print_subsection "ultimo estado runtime (via helper readonly)"
    printf '%s\n' "${helper_output}" | redact_sensitive_output
  else
    echo
    notice_line warning "El estado runtime de Telegram no es legible desde esta sesion."
  fi
  echo
  notice_line readonly "La ejecucion real de comandos sigue ocurriendo via bot, policy y auditoria del broker."
}

show_openclaw_capabilities() {
  local cli_output rc=0 helper_output
  print_header
  print_section_title "OpenClaw / capacidades"
  echo
  kv_line "policy_source" "$(openclaw_policy_source_display)"
  kv_line "policy_path" "$(openclaw_policy_path_display)"
  echo
  if ! openclaw_broker_cli_available; then
    notice_line error "CLI del broker no disponible desde esta sesion."
    return 0
  fi
  cat <<'EOF'
[READONLY] readonly: visible para operador/viewer
[SUCCESS]  allowed=yes: la accion podria ejecutarse ahora mismo
[MUTATING] restricted: accion mutante o sensible
EOF
  echo
  cli_output="$(run_openclaw_broker_cli show --format console 2>&1)" || rc=$?
  if [[ "${rc}" -eq 0 ]]; then
    printf '%s\n' "${cli_output}" | redact_sensitive_output
  elif printf '%s' "${cli_output}" | grep -q 'PermissionError:'; then
    if helper_output="$(run_openclaw_readonly_helper broker_state_console 2>/dev/null)"; then
      echo
      notice_line readonly "Usando helper readonly root-owned para leer el runtime real."
      printf '%s\n' "${helper_output}" | redact_sensitive_output
    else
      echo
      notice_line error "No se pudo leer el estado efectivo del broker desde esta sesion."
      kv_line "runtime_state" "${OPENCLAW_BROKER_RUNTIME_STATE}"
      notice_line warning "El estado runtime del broker existe pero no es legible con los permisos actuales."
    fi
  else
    printf '%s\n' "${cli_output}" | redact_sensitive_output
    echo
    notice_line error "No se pudo leer el estado efectivo del broker desde esta sesion."
    notice_line warning "Posible causa: policy no visible o permisos insuficientes."
  fi
}

show_openclaw_capabilities_audit() {
  local cli_output rc=0 helper_output
  print_header
  print_section_title "OpenClaw / auditoria de capacidades"
  echo
  if ! openclaw_broker_cli_available; then
    notice_line error "CLI del broker no disponible desde esta sesion."
    return 0
  fi
  notice_line readonly "Solo lectura; por Telegram, /audit_tail puede quedar reservado a admin."
  echo
  cli_output="$(run_openclaw_broker_cli audit-tail --lines 20 --format console 2>&1)" || rc=$?
  if [[ "${rc}" -eq 0 ]]; then
    printf '%s\n' "${cli_output}" | redact_sensitive_output
  elif printf '%s' "${cli_output}" | grep -q 'PermissionError:'; then
    if helper_output="$(run_openclaw_readonly_helper broker_audit_recent 2>/dev/null)"; then
      notice_line readonly "Usando helper readonly root-owned para leer auditoria reciente."
      printf '%s\n' "${helper_output}" | redact_sensitive_output
    else
      notice_line error "No se pudo leer la auditoria del broker desde esta sesion."
      kv_line "runtime_state" "${OPENCLAW_BROKER_RUNTIME_STATE}"
      notice_line warning "La auditoria vive en el runtime del broker y no es legible con los permisos actuales."
    fi
  else
    printf '%s\n' "${cli_output}" | redact_sensitive_output
    notice_line error "No se pudo leer la auditoria del broker desde esta sesion."
  fi
}

known_action_label() {
  case "$1" in
    action.health.general.v1) printf '%s\n' "Health general" ;;
    action.logs.read.v1) printf '%s\n' "Lectura de logs" ;;
    action.webhook.trigger.v1) printf '%s\n' "Disparo controlado" ;;
    action.openclaw.restart.v1) printf '%s\n' "Reinicio OpenClaw" ;;
    action.dropzone.write.v1) printf '%s\n' "Escritura drop-zone" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

known_action_permission() {
  case "$1" in
    action.health.general.v1|action.logs.read.v1) printf '%s\n' "operator.read" ;;
    action.webhook.trigger.v1) printf '%s\n' "operator.trigger" ;;
    action.openclaw.restart.v1) printf '%s\n' "operator.control" ;;
    action.dropzone.write.v1) printf '%s\n' "operator.write" ;;
    *) printf '%s\n' "unknown" ;;
  esac
}

known_action_description() {
  case "$1" in
    action.health.general.v1) printf '%s\n' "Health general fijo del boundary OpenClaw/inference-gateway." ;;
    action.logs.read.v1) printf '%s\n' "Lectura controlada de logs permitidos por stream_id." ;;
    action.webhook.trigger.v1) printf '%s\n' "Disparo de webhook controlado para operaciones acotadas." ;;
    action.openclaw.restart.v1) printf '%s\n' "Reservado a control administrativo; sigue siendo la accion mas sensible." ;;
    action.dropzone.write.v1) printf '%s\n' "Escritura limitada en la drop-zone controlada del broker." ;;
    *) printf '%s\n' "Accion no catalogada en esta consola." ;;
  esac
}

known_action_badge() {
  case "$1" in
    action.health.general.v1|action.logs.read.v1) badge readonly "READONLY" ;;
    action.openclaw.restart.v1) badge warning "CONTROL" ;;
    *) badge mutating "RESTRICTED" ;;
  esac
}

print_known_action_card() {
  local action_id="$1"
  printf '%s %s\n' "$(known_action_badge "${action_id}")" "$(known_action_label "${action_id}")"
  kv_line "action_id" "${action_id}"
  kv_line "permission" "$(known_action_permission "${action_id}")"
  kv_line "descripcion" "$(known_action_description "${action_id}")"
  echo
}

show_openclaw_action_catalog() {
  print_header
  print_section_title "OpenClaw / catalogo de acciones"
  echo
  print_subsection "acciones conocidas en el boundary actual"
  print_known_action_card "action.health.general.v1"
  print_known_action_card "action.logs.read.v1"
  print_known_action_card "action.webhook.trigger.v1"
  print_known_action_card "action.dropzone.write.v1"
  print_known_action_card "action.openclaw.restart.v1"
  notice_line info "Las acciones readonly forman parte de la observabilidad base."
  notice_line warning "Las acciones restricted/control deben abrirse con TTL corto y motivo claro."
}

show_operational_overview() {
  local docker_status cli_status helper_status
  print_header
  print_section_title "Resumen operativo"
  echo
  if docker_available; then
    docker_status="$(badge success yes)"
  else
    docker_status="$(badge warning no)"
  fi
  if openclaw_broker_cli_available; then
    cli_status="$(badge success yes)"
  else
    cli_status="$(badge warning no)"
  fi
  if openclaw_readonly_helper_available; then
    helper_status="$(badge success yes)"
  else
    helper_status="$(badge warning no)"
  fi
  print_subsection "estado ejecutivo"
  kv_line "host" "$(hostname 2>/dev/null || printf '%s' 'unknown')"
  kv_line "session_operator" "$(openclaw_operator_identity)"
  kv_line "docker_access" "${docker_status}"
  kv_line "broker_cli_available" "${cli_status}"
  kv_line "readonly_helper" "${helper_status}"
  kv_line "policy_source" "$(openclaw_policy_source_display)"
  kv_line "policy_path" "$(openclaw_policy_path_display)"
  echo
  print_subsection "servicios clave"
  kv_line "inference_gateway" "$(service_active_state "${INFERENCE_GATEWAY_SERVICE}") / $(service_sub_state "${INFERENCE_GATEWAY_SERVICE}")"
  kv_line "telegram_bot" "$(service_active_state "${OPENCLAW_TELEGRAM_SERVICE}") / $(service_sub_state "${OPENCLAW_TELEGRAM_SERVICE}")"
  kv_line "openclaw_runtime_root" "$([[ -d "${OPENCLAW_RUNTIME_ROOT}" ]] && badge success yes || badge warning no)"
  kv_line "broker_state_access" "$(runtime_access_badge "${OPENCLAW_BROKER_RUNTIME_STATE}")"
  kv_line "broker_audit_access" "$(runtime_access_badge "${OPENCLAW_BROKER_AUDIT_LOG}")"
  kv_line "telegram_runtime_access" "$(runtime_access_badge "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}")"
  echo
  print_subsection "superficie funcional"
  notice_line readonly "Health y logs forman parte de la observabilidad base."
  notice_line info "Telegram esta integrado como canal operativo corto: /status /capabilities /audit_tail /execute."
  notice_line mutating "Broker y capacidades permiten mutacion controlada via policy/TTL."
  if openclaw_readonly_helper_available; then
    notice_line success "El helper readonly del host esta disponible para leer runtime real sin abrir acceso general."
  fi
  echo
  print_subsection "siguiente comprobacion sugerida"
  if [[ -r "${OPENCLAW_BROKER_RUNTIME_STATE}" ]] || openclaw_readonly_helper_available; then
    echo "- Revisar estado efectivo del broker y auditoria."
  else
    echo "- Resolver acceso readonly al runtime del broker para ver estado y auditoria real."
  fi
  if [[ "$(service_active_state "${OPENCLAW_TELEGRAM_SERVICE}")" == "active" ]] && { [[ -r "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}" ]] || openclaw_readonly_helper_available; }; then
    echo "- Validar Telegram runtime y ultimos eventos si se abre acceso a logs/runtime status."
  else
    echo "- Revisar Telegram service antes de habilitar controles mutantes."
  fi
}

show_openclaw_runtime_diagnostics() {
  local cli_status docker_status systemctl_status helper_status
  print_header
  print_section_title "OpenClaw / diagnostico operativo"
  echo
  if openclaw_broker_cli_available; then
    cli_status="$(badge success yes)"
  else
    cli_status="$(badge warning no)"
  fi
  if docker_available; then
    docker_status="$(badge success yes)"
  else
    docker_status="$(badge warning no)"
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl_status="$(badge success yes)"
  else
    systemctl_status="$(badge warning no)"
  fi
  if openclaw_readonly_helper_available; then
    helper_status="$(badge success yes)"
  else
    helper_status="$(badge warning no)"
  fi
  print_subsection "sesion actual"
  kv_line "operator_id_sugerido" "$(openclaw_operator_identity)"
  kv_line "broker_cli_available" "${cli_status}"
  kv_line "docker_access" "${docker_status}"
  kv_line "systemctl_available" "${systemctl_status}"
  kv_line "readonly_helper" "${helper_status}"
  echo
  print_subsection "runtime y permisos"
  kv_line "runtime_root" "${OPENCLAW_RUNTIME_ROOT}"
  kv_line "runtime_root_exists" "$([[ -d "${OPENCLAW_RUNTIME_ROOT}" ]] && badge success yes || badge warning no)"
  kv_line "compose_readable" "$([[ -r "${OPENCLAW_RUNTIME_COMPOSE}" ]] && badge success yes || badge warning no)"
  kv_line "policy_runtime_readable" "$([[ -r "${OPENCLAW_RESTRICTED_OPERATOR_POLICY_RUNTIME}" ]] && badge success yes || badge warning no)"
  kv_line "broker_state_access" "$(runtime_access_badge "${OPENCLAW_BROKER_RUNTIME_STATE}")"
  kv_line "broker_audit_access" "$(runtime_access_badge "${OPENCLAW_BROKER_AUDIT_LOG}")"
  kv_line "telegram_runtime_access" "$(runtime_access_badge "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}")"
  echo
  print_subsection "servicios"
  kv_line "inference_gateway" "$(service_active_state "${INFERENCE_GATEWAY_SERVICE}") / pid=$(service_main_pid "${INFERENCE_GATEWAY_SERVICE}")"
  kv_line "telegram_bot" "$(service_active_state "${OPENCLAW_TELEGRAM_SERVICE}") / pid=$(service_main_pid "${OPENCLAW_TELEGRAM_SERVICE}")"
  echo
  print_subsection "degradaciones detectadas"
  if [[ ! -r "${OPENCLAW_BROKER_RUNTIME_STATE}" ]] && ! openclaw_readonly_helper_available; then
    notice_line warning "La consola no puede leer el estado vivo del broker con los permisos actuales."
  fi
  if [[ ! -r "${OPENCLAW_BROKER_AUDIT_LOG}" ]] && ! openclaw_readonly_helper_available; then
    notice_line warning "La auditoria real del broker no es legible desde esta sesion."
  fi
  if [[ ! -r "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}" ]] && ! openclaw_readonly_helper_available; then
    notice_line warning "telegram_runtime_status.json no es legible; solo se ve el estado systemd."
  fi
  if [[ -r "${OPENCLAW_BROKER_RUNTIME_STATE}" && -r "${OPENCLAW_BROKER_AUDIT_LOG}" && -r "${OPENCLAW_TELEGRAM_RUNTIME_STATUS}" ]]; then
    notice_line success "La sesion tiene visibilidad readonly suficiente sobre runtime y auditoria."
  elif openclaw_readonly_helper_available; then
    notice_line success "El helper readonly del host compensa la falta de lectura directa sobre runtime."
  fi
}

select_mutating_action_id() {
  local action_choice custom_action
  if [[ ! -t 0 ]]; then
    prompt_optional 'action_id'
    return 0
  fi
  if ! inline_menu_choice_with_fallback "seleccion de accion mutante" MUTATING_ACTION_OPTIONS show_mutating_action_menu "Selecciona una accion: " action_choice; then
    return 1
  fi
  case "${action_choice}" in
    1) printf '%s\n' "action.webhook.trigger.v1" ;;
    2) printf '%s\n' "action.dropzone.write.v1" ;;
    3) printf '%s\n' "action.openclaw.restart.v1" ;;
    8)
      custom_action="$(prompt_optional 'action_id')"
      if [[ -z "${custom_action}" ]]; then
        return 1
      fi
      printf '%s\n' "${custom_action}"
      ;;
    9) return 1 ;;
    *)
      echo "Opcion no valida."
      return 1
      ;;
  esac
}

show_mutating_action_menu() {
  print_subsection "seleccion de accion mutante"
  menu_line "1" "Disparo controlado" "$(badge mutating "action.webhook.trigger.v1")"
  menu_line "2" "Escritura drop-zone" "$(badge mutating "action.dropzone.write.v1")"
  menu_line "3" "Reinicio OpenClaw" "$(badge warning "action.openclaw.restart.v1")"
  menu_line "8" "Introducir action_id manual"
  menu_line "9" "Cancelar"
}

security_preset_title() {
  case "$1" in
    readonly-strict) printf '%s\n' "Observacion estricta" ;;
    trigger-window) printf '%s\n' "Disparo controlado" ;;
    dropzone-window) printf '%s\n' "Escritura temporal" ;;
    operator-temporal) printf '%s\n' "Operador temporal" ;;
    admin-window) printf '%s\n' "Admin restringido" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

security_preset_default_ttl() {
  case "$1" in
    readonly-strict) printf '%s\n' "" ;;
    trigger-window) printf '%s\n' "10" ;;
    dropzone-window) printf '%s\n' "15" ;;
    operator-temporal) printf '%s\n' "15" ;;
    admin-window) printf '%s\n' "10" ;;
    *) printf '%s\n' "" ;;
  esac
}

security_preset_warning() {
  case "$1" in
    readonly-strict)
      printf '%s\n' "Reduce la superficie mutante a solo observabilidad. No afecta acciones readonly."
      ;;
    trigger-window)
      printf '%s\n' "Abre solo el disparo controlado. Recomendado para ventanas muy cortas."
      ;;
    dropzone-window)
      printf '%s\n' "Abre solo la escritura en drop-zone. Mantiene webhook y restart cerrados."
      ;;
    operator-temporal)
      printf '%s\n' "Abre la operativa habitual de operador con TTL corto. Restart sigue cerrado."
      ;;
    admin-window)
      printf '%s\n' "Abre tambien restart. Usar solo con operador admin y motivo fuerte."
      ;;
    *)
      printf '%s\n' "Preset sin advertencia catalogada."
      ;;
  esac
}

security_preset_plan() {
  case "$1" in
    readonly-strict)
      printf '%s\n' \
        "disable|action.webhook.trigger.v1" \
        "disable|action.dropzone.write.v1" \
        "disable|action.openclaw.restart.v1"
      ;;
    trigger-window)
      printf '%s\n' \
        "enable_ttl|action.webhook.trigger.v1" \
        "disable|action.dropzone.write.v1" \
        "disable|action.openclaw.restart.v1"
      ;;
    dropzone-window)
      printf '%s\n' \
        "disable|action.webhook.trigger.v1" \
        "enable_ttl|action.dropzone.write.v1" \
        "disable|action.openclaw.restart.v1"
      ;;
    operator-temporal)
      printf '%s\n' \
        "enable_ttl|action.webhook.trigger.v1" \
        "enable_ttl|action.dropzone.write.v1" \
        "disable|action.openclaw.restart.v1"
      ;;
    admin-window)
      printf '%s\n' \
        "enable_ttl|action.webhook.trigger.v1" \
        "enable_ttl|action.dropzone.write.v1" \
        "enable_ttl|action.openclaw.restart.v1"
      ;;
    *)
      return 1
      ;;
  esac
}

show_security_presets_catalog() {
  print_header
  print_section_title "OpenClaw / seguridad / presets"
  echo
  print_subsection "presets disponibles"
  menu_line "1" "Observacion estricta" "$(badge readonly "LOCKDOWN")"
  echo "    Solo observabilidad. Deshabilita webhook, drop-zone y restart."
  menu_line "2" "Disparo controlado" "$(badge mutating "TTL 10m")"
  echo "    Abre solo action.webhook.trigger.v1 durante una ventana corta."
  menu_line "3" "Escritura temporal" "$(badge mutating "TTL 15m")"
  echo "    Abre solo action.dropzone.write.v1 con TTL corto."
  menu_line "4" "Operador temporal" "$(badge mutating "TTL 15m")"
  echo "    Abre webhook + drop-zone para operativa habitual; restart sigue cerrado."
  menu_line "5" "Admin restringido" "$(badge warning "TTL 10m")"
  echo "    Abre tambien restart. Debe usarlo un operador con permisos admin."
  echo
  notice_line warning "Todos los presets mutantes exigen confirmacion explicita y dejan rastro en auditoria."
}

show_security_preset_preview() {
  local preset="$1"
  local operator="$2"
  local reason="$3"
  local ttl_minutes="$4"
  local operation action_id

  print_header
  print_section_title "OpenClaw / seguridad / previsualizacion"
  echo
  kv_line "preset" "$(security_preset_title "${preset}")"
  kv_line "operator_id" "${operator}"
  kv_line "reason" "${reason}"
  if [[ -n "${ttl_minutes}" ]]; then
    kv_line "ttl_minutes" "${ttl_minutes}"
  fi
  echo
  print_subsection "advertencia"
  notice_line warning "$(security_preset_warning "${preset}")"
  echo
  print_subsection "cambios previstos"
  while IFS='|' read -r operation action_id; do
    [[ -z "${operation}" ]] && continue
    case "${operation}" in
      enable_ttl)
        echo "- ENABLE TTL ${ttl_minutes}m :: $(known_action_label "${action_id}") (${action_id})"
        ;;
      disable)
        echo "- DISABLE :: $(known_action_label "${action_id}") (${action_id})"
        ;;
    esac
  done < <(security_preset_plan "${preset}")
  echo
  notice_line info "La consola aplicara cada cambio via broker CLI y mostrara el resultado paso a paso."
}

confirm_security_apply() {
  local phrase
  if [[ ! -t 0 ]]; then
    notice_line warning "Sesion no interactiva: la aplicacion del preset se cancela por seguridad."
    return 1
  fi
  printf 'Escribe APPLY para continuar: '
  read -r phrase
  if [[ "${phrase}" != "APPLY" ]]; then
    notice_line warning "Operacion cancelada; no se aplico ningun cambio."
    return 1
  fi
  return 0
}

apply_security_preset_flow() {
  local preset="$1"
  local operator reason ttl_minutes default_ttl operation action_id failures=0
  local change_reason rollback_reason rollback_action rollback_failures=0
  local successful_rollbacks=()

  if ! openclaw_broker_cli_available; then
    notice_line error "CLI del broker no disponible desde esta sesion."
    return 1
  fi

  operator="$(resolve_openclaw_operator_identity)" || return 1
  default_ttl="$(security_preset_default_ttl "${preset}")"
  if [[ -n "${default_ttl}" ]]; then
    ttl_minutes="$(prompt_with_default 'ttl_minutes' "${default_ttl}")"
    if [[ -z "${ttl_minutes}" ]]; then
      echo "ttl_minutes requerido."
      return 1
    fi
  else
    ttl_minutes=""
  fi
  reason="$(prompt_with_default 'motivo' "preset_$(printf '%s' "${preset}" | tr '-' '_')")"
  show_security_preset_preview "${preset}" "${operator}" "${reason}" "${ttl_minutes}"
  if ! confirm_security_apply; then
    return 1
  fi

  while IFS='|' read -r operation action_id; do
    [[ -z "${operation}" ]] && continue
    printf '\n'
    print_subsection "$(known_action_label "${action_id}")"
    change_reason="${reason}:${preset}"
    case "${operation}" in
      enable_ttl)
        if apply_openclaw_capability_change \
          "$(security_preset_title "${preset}")" \
          enable --action-id "${action_id}" --ttl-minutes "${ttl_minutes}" --operator-id "${operator}" --reason "${change_reason}"; then
          successful_rollbacks+=("${action_id}")
        else
          failures=$((failures + 1))
        fi
        ;;
      enable)
        if apply_openclaw_capability_change \
          "$(security_preset_title "${preset}")" \
          enable --action-id "${action_id}" --operator-id "${operator}" --reason "${change_reason}"; then
          successful_rollbacks+=("${action_id}")
        else
          failures=$((failures + 1))
        fi
        ;;
      disable)
        if ! apply_openclaw_capability_change \
          "$(security_preset_title "${preset}")" \
          disable --action-id "${action_id}" --operator-id "${operator}" --reason "${change_reason}"; then
          failures=$((failures + 1))
        fi
        ;;
      *)
        notice_line error "Operacion de preset no soportada: ${operation} (${action_id})"
        failures=$((failures + 1))
        ;;
    esac
  done < <(security_preset_plan "${preset}")

  printf '\n'
  if [[ "${failures}" -eq 0 ]]; then
    notice_line success "Preset aplicado correctamente: $(security_preset_title "${preset}")"
    return 0
  fi

  notice_line error "Preset fallido: ${failures} cambios no se pudieron completar."
  if [[ "${#successful_rollbacks[@]}" -gt 0 ]]; then
    notice_line warning "Se detecto una apertura parcial. Ejecutando rollback automatico por seguridad."
    rollback_reason="${reason}:${preset}:auto_rollback"
    for rollback_action in "${successful_rollbacks[@]}"; do
      printf '\n'
      print_subsection "rollback :: $(known_action_label "${rollback_action}")"
      if ! apply_openclaw_capability_change \
        "$(security_preset_title "${preset}") / rollback" \
        disable --action-id "${rollback_action}" --operator-id "${operator}" --reason "${rollback_reason}"; then
        rollback_failures=$((rollback_failures + 1))
      fi
    done
    printf '\n'
    if [[ "${rollback_failures}" -eq 0 ]]; then
      notice_line warning "Rollback automatico completado. Se revirtieron las aperturas aplicadas por el preset."
    else
      notice_line error "Rollback automatico incompleto: ${rollback_failures} cambios no se pudieron revertir."
    fi
  else
    notice_line warning "No hubo aperturas exitosas que revertir automaticamente."
  fi
  return 1
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
    notice_line success "Cambio aplicado: ${subcommand}"
    return 0
  fi
  printf '%s\n' "${cli_output}" | redact_sensitive_output
  echo
  notice_line error "No se pudo aplicar ${subcommand} desde esta sesion."
  if printf '%s' "${cli_output}" | grep -q 'operator_not_authorized'; then
    notice_line warning "Causa probable: el operator_id actual no tiene permiso suficiente para esta accion."
  elif printf '%s' "${cli_output}" | grep -q 'unknown_action'; then
    notice_line warning "Causa probable: action_id no reconocido por la policy viva."
  elif printf '%s' "${cli_output}" | grep -q 'invalid datetime'; then
    notice_line warning "Causa probable: TTL o fecha de expiracion invalida."
  else
    notice_line warning "Causa probable: policy no visible, permisos insuficientes o validacion rechazada."
  fi
  return 1
}

openclaw_capability_enable_flow() {
  local action_id reason operator
  action_id="$(select_mutating_action_id)" || return 1
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
  action_id="$(select_mutating_action_id)" || return 1
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
  action_id="$(select_mutating_action_id)" || return 1
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
  action_id="$(select_mutating_action_id)" || return 1
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
  print_section_title "Ayuda / limites del MVP"
  echo
  cat <<'EOF'
[READONLY] La consola prioriza observabilidad, diagnostico y verificacion operativa.
[MUTATING] La mutacion existe solo en broker/capacidades y seguridad/control.
- Dashboard inicial para situacion general del host, OpenClaw, broker y Telegram.
- Menus separados para runtime, broker, seguridad, evidencias y diagnostico.
- Presets guiados de seguridad con TTL corto, motivo obligatorio y confirmacion explicita.
[WARNING] No toca secretos ni reinicia servicios directamente desde esta sesion.
- Si una comprobacion requiere Docker o sudo y no esta disponible, la consola degrada con mensaje claro.
- Si el helper readonly root-owned esta instalado, la consola puede leer runtime real de broker y Telegram sin acceso general a /opt/automation.
- Telegram se trata como canal operativo real: status service, runtime status y comandos soportados.
- Broker y capacidades usan la CLI real del restricted operator; no se inventan acciones fuera de policy.
- La fuente de verdad operativa sigue siendo runtime + auditoria; la plantilla del repo es fallback declarativo.
[WARNING] Para acciones sensibles: usar TTL corto, motivo claro y revisar auditoria despues.
EOF
}

interactive_menu_render() {
  local title="$1"
  local options_name="$2"
  local selected_index="$3"
  local -n options_ref="${options_name}"
  local option_id option_label
  local index
  local active_cursor="${COLOR_BOLD}${COLOR_CYAN}❯${COLOR_RESET}"
  local active_label_style="${COLOR_BOLD}${COLOR_WHITE}"

  printf '\r\033[2K%b%s%b\n' "${COLOR_BOLD}${COLOR_WHITE}" "${title}" "${COLOR_RESET}" > /dev/tty
  printf '\r\033[2K\n' > /dev/tty
  for index in "${!options_ref[@]}"; do
    IFS='|' read -r option_id option_label <<< "${options_ref[${index}]}"
    if [[ "${index}" -eq "${selected_index}" ]]; then
      printf '\r\033[2K %b %b%s%b\n' "${active_cursor}" "${active_label_style}" "${option_label}" "${COLOR_RESET}" > /dev/tty
    else
      printf '\r\033[2K   %s\n' "${option_label}" > /dev/tty
    fi
  done
  printf '\r\033[2K\n' > /dev/tty
  printf '\r\033[2K%b%s%b\n' "${COLOR_DIM}" "Usa ↑/↓ y Enter para seleccionar." "${COLOR_RESET}" > /dev/tty
}

interactive_menu() {
  local title="$1"
  local options_name="$2"
  local result_var="${3:-INTERACTIVE_MENU_RESULT}"
  local -n options_ref="${options_name}"
  local selected_index=0
  local rendered_lines
  local key escape_1 escape_2
  local selected_id selected_label

  if [[ ! -t 0 || ! -t 1 || ! -r /dev/tty ]]; then
    return 1
  fi
  if [[ "${#options_ref[@]}" -eq 0 ]]; then
    return 1
  fi

  rendered_lines=$(( ${#options_ref[@]} + 4 ))
  printf '\033[?25l' > /dev/tty
  interactive_menu_render "${title}" "${options_name}" "${selected_index}"

  while true; do
    if ! IFS= read -rsn1 key < /dev/tty; then
      printf '\033[?25h' > /dev/tty
      return 1
    fi

    case "${key}" in
      "")
        IFS='|' read -r selected_id selected_label <<< "${options_ref[${selected_index}]}"
        printf '\033[?25h' > /dev/tty
        printf -v "${result_var}" '%s' "${selected_id}"
        return 0
        ;;
      $'\x1b')
        escape_1=""
        escape_2=""
        IFS= read -rsn1 -t 0.05 escape_1 < /dev/tty || true
        if [[ "${escape_1}" == "[" ]]; then
          IFS= read -rsn1 -t 0.05 escape_2 < /dev/tty || true
          case "${escape_2}" in
            A)
              selected_index=$(( (selected_index - 1 + ${#options_ref[@]}) % ${#options_ref[@]} ))
              ;;
            B)
              selected_index=$(( (selected_index + 1) % ${#options_ref[@]} ))
              ;;
          esac
        fi
        ;;
      k)
        selected_index=$(( (selected_index - 1 + ${#options_ref[@]}) % ${#options_ref[@]} ))
        ;;
      j)
        selected_index=$(( (selected_index + 1) % ${#options_ref[@]} ))
        ;;
      *)
        continue
        ;;
    esac

    printf '\033[%dA' "${rendered_lines}" > /dev/tty
    interactive_menu_render "${title}" "${options_name}" "${selected_index}"
  done
}

menu_choice_with_fallback() {
  local title="$1"
  local options_name="$2"
  local fallback_fn="$3"
  local prompt="$4"
  local result_var="${5:-MENU_CHOICE}"
  local selection

  if [[ -t 0 && -t 1 ]]; then
    print_header
    if interactive_menu "${title}" "${options_name}" "${result_var}"; then
      return 0
    fi
  fi

  "${fallback_fn}"
  printf '%s' "${prompt}"
  read -r selection
  printf -v "${result_var}" '%s' "${selection}"
}

inline_menu_choice_with_fallback() {
  local title="$1"
  local options_name="$2"
  local fallback_fn="$3"
  local prompt="$4"
  local result_var="${5:-MENU_CHOICE}"
  local selection

  if [[ -t 0 && -t 1 ]]; then
    if interactive_menu "${title}" "${options_name}" "${result_var}"; then
      return 0
    fi
  fi

  "${fallback_fn}"
  printf '%s' "${prompt}"
  read -r selection
  printf -v "${result_var}" '%s' "${selection}"
}

show_menu() {
  print_header
  print_section_title "  [ MENÚ PRINCIPAL ]"
  echo
  menu_line "1" "📊 Resumen operativo"
  menu_line "2" "🌐 OpenClaw y Telegram"
  menu_line "3" "⚙️ Broker y capacidades"
  menu_line "4" "🔒 Seguridad y control"
  menu_line "5" "📑 Evidencias e informes"
  menu_line "6" "🛠️ Diagnostico"
  menu_line "7" "❓ Ayuda / limites del MVP"
  echo
  menu_line "9" "🚪 Salir"
  echo
  subrule
  printf '%s\n' "$(badge readonly "READONLY") observabilidad, evidencias y diagnostico"
  printf '%s\n' "$(badge mutating "MUTATING") broker/capacidades y presets de seguridad"
  subrule
}

declare -a MAIN_MENU_OPTIONS
declare -a OPENCLAW_MENU_OPTIONS
declare -a BROKER_MENU_OPTIONS
declare -a SECURITY_MENU_OPTIONS
declare -a DIAGNOSTICS_MENU_OPTIONS
declare -a OPENCLAW_CAPABILITIES_MENU_OPTIONS
declare -a MUTATING_ACTION_OPTIONS

init_menu_options() {
  MAIN_MENU_OPTIONS=(
    "1|📊 Resumen operativo"
    "2|🌐 OpenClaw y Telegram"
    "3|⚙️ Broker y capacidades"
    "4|🔒 Seguridad y control"
    "5|📑 Evidencias e informes"
    "6|🛠️ Diagnostico"
    "7|❓ Ayuda / limites del MVP"
    "9|🚪 Salir"
  )

  OPENCLAW_MENU_OPTIONS=(
    "1|Resumen runtime OpenClaw"
    "2|Telegram runtime"
    "3|Logs utiles"
    "4|Health"
    "5|Catalogo de acciones"
    "9|Volver"
  )

  BROKER_MENU_OPTIONS=(
    "1|Estado efectivo"
    "2|Auditoria reciente"
    "3|Catalogo de acciones"
    "4|Control manual por accion $(badge mutating "GUIADO")"
    "5|Diagnostico broker/runtime"
    "9|Volver"
  )

  SECURITY_MENU_OPTIONS=(
    "1|Ver catalogo de presets $(badge readonly "READONLY")"
    "2|Aplicar observacion estricta $(badge readonly "LOCKDOWN")"
    "3|Aplicar disparo controlado $(badge mutating "TTL 10m")"
    "4|Aplicar escritura temporal $(badge mutating "TTL 15m")"
    "5|Aplicar operador temporal $(badge mutating "TTL 15m")"
    "6|Aplicar admin restringido $(badge warning "TTL 10m")"
    "7|Resetear one-shot manual $(badge mutating "MANUAL")"
    "8|Diagnostico broker/runtime $(badge readonly "READONLY")"
    "9|Volver"
  )

  DIAGNOSTICS_MENU_OPTIONS=(
    "1|Resumen operativo"
    "2|Estado general del host"
    "3|Estado de Docker"
    "4|Red / listeners / puertos clave"
    "5|Zona de agentes"
    "6|Diagnostico OpenClaw / broker"
    "7|Estado de n8n"
    "8|Evidencias e informes"
    "9|Volver"
  )

  OPENCLAW_CAPABILITIES_MENU_OPTIONS=(
    "1|Ver estado efectivo $(badge readonly "READONLY")"
    "2|Habilitar accion $(badge mutating "MUTATING")"
    "3|Deshabilitar accion $(badge mutating "MUTATING")"
    "4|Habilitar accion con TTL $(badge mutating "MUTATING")"
    "5|Resetear one-shot consumido $(badge mutating "MUTATING")"
    "6|Ver auditoria reciente $(badge readonly "READONLY")"
    "7|Catalogo de acciones $(badge readonly "READONLY")"
    "8|Diagnostico broker/runtime $(badge readonly "READONLY")"
    "9|Volver"
  )

  MUTATING_ACTION_OPTIONS=(
    "1|Disparo controlado $(badge mutating "action.webhook.trigger.v1")"
    "2|Escritura drop-zone $(badge mutating "action.dropzone.write.v1")"
    "3|Reinicio OpenClaw $(badge warning "action.openclaw.restart.v1")"
    "8|Introducir action_id manual"
    "9|Cancelar"
  )
}

show_openclaw_menu() {
  print_header
  print_section_title "OpenClaw y Telegram"
  echo
  menu_line "1" "Resumen runtime OpenClaw"
  menu_line "2" "Telegram runtime"
  menu_line "3" "Logs utiles"
  menu_line "4" "Health"
  menu_line "5" "Catalogo de acciones"
  menu_line "9" "Volver"
}

show_broker_menu() {
  print_header
  print_section_title "Broker y capacidades"
  echo
  menu_line "1" "Estado efectivo"
  menu_line "2" "Auditoria reciente"
  menu_line "3" "Catalogo de acciones"
  menu_line "4" "Control manual por accion" "$(badge mutating "GUIADO")"
  menu_line "5" "Diagnostico broker/runtime"
  menu_line "9" "Volver"
}

show_security_menu() {
  print_header
  print_section_title "Seguridad y control"
  echo
  menu_line "1" "Ver catalogo de presets" "$(badge readonly "READONLY")"
  menu_line "2" "Aplicar observacion estricta" "$(badge readonly "LOCKDOWN")"
  menu_line "3" "Aplicar disparo controlado" "$(badge mutating "TTL 10m")"
  menu_line "4" "Aplicar escritura temporal" "$(badge mutating "TTL 15m")"
  menu_line "5" "Aplicar operador temporal" "$(badge mutating "TTL 15m")"
  menu_line "6" "Aplicar admin restringido" "$(badge warning "TTL 10m")"
  menu_line "7" "Resetear one-shot manual" "$(badge mutating "MANUAL")"
  menu_line "8" "Diagnostico broker/runtime" "$(badge readonly "READONLY")"
  menu_line "9" "Volver"
}

show_diagnostics_menu() {
  print_header
  print_section_title "Diagnostico"
  echo
  menu_line "1" "Resumen operativo"
  menu_line "2" "Estado general del host"
  menu_line "3" "Estado de Docker"
  menu_line "4" "Red / listeners / puertos clave"
  menu_line "5" "Zona de agentes"
  menu_line "6" "Diagnostico OpenClaw / broker"
  menu_line "7" "Estado de n8n"
  menu_line "8" "Evidencias e informes"
  menu_line "9" "Volver"
}

show_openclaw_capabilities_menu() {
  print_header
  print_section_title "Broker / control manual"
  echo
  menu_line "1" "Ver estado efectivo" "$(badge readonly "READONLY")"
  menu_line "2" "Habilitar accion" "$(badge mutating "MUTATING")"
  menu_line "3" "Deshabilitar accion" "$(badge mutating "MUTATING")"
  menu_line "4" "Habilitar accion con TTL" "$(badge mutating "MUTATING")"
  menu_line "5" "Resetear one-shot consumido" "$(badge mutating "MUTATING")"
  menu_line "6" "Ver auditoria reciente" "$(badge readonly "READONLY")"
  menu_line "7" "Catalogo de acciones" "$(badge readonly "READONLY")"
  menu_line "8" "Diagnostico broker/runtime" "$(badge readonly "READONLY")"
  menu_line "9" "Volver"
}

run_openclaw_section() {
  case "$1" in
    1|status) show_openclaw_status ;;
    2|telegram) show_openclaw_telegram_runtime ;;
    3|logs) show_openclaw_logs ;;
    4|health) show_openclaw_health ;;
    5|actions) show_openclaw_action_catalog ;;
    9|back) return 1 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 2
      ;;
  esac
}

run_broker_section() {
  case "$1" in
    1|show) show_openclaw_capabilities ;;
    2|audit) show_openclaw_capabilities_audit ;;
    3|catalog) show_openclaw_action_catalog ;;
    4|manual)
      while true; do
        menu_choice_with_fallback "Broker / control manual" OPENCLAW_CAPABILITIES_MENU_OPTIONS show_openclaw_capabilities_menu "Selecciona una opcion: " openclaw_cap_choice
        case "${openclaw_cap_choice}" in
          1) show_openclaw_capabilities ;;
          2) openclaw_capability_enable_flow ;;
          3) openclaw_capability_disable_flow ;;
          4) openclaw_capability_ttl_flow ;;
          5) openclaw_capability_reset_one_shot_flow ;;
          6) show_openclaw_capabilities_audit ;;
          7) show_openclaw_action_catalog ;;
          8) show_openclaw_runtime_diagnostics ;;
          9) break ;;
          *)
            echo "Opcion no valida: ${openclaw_cap_choice}" >&2
            ;;
        esac
        pause_if_interactive
      done
      ;;
    5|diag) show_openclaw_runtime_diagnostics ;;
    9|back) return 1 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 2
      ;;
  esac
}

run_security_section() {
  case "$1" in
    1|catalog) show_security_presets_catalog ;;
    2|readonly-strict) apply_security_preset_flow "readonly-strict" ;;
    3|trigger-window) apply_security_preset_flow "trigger-window" ;;
    4|dropzone-window) apply_security_preset_flow "dropzone-window" ;;
    5|operator-temporal) apply_security_preset_flow "operator-temporal" ;;
    6|admin-window) apply_security_preset_flow "admin-window" ;;
    7|reset-one-shot) openclaw_capability_reset_one_shot_flow ;;
    8|diag) show_openclaw_runtime_diagnostics ;;
    9|back) return 1 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 2
      ;;
  esac
}

run_diagnostics_section() {
  case "$1" in
    1|overview) show_operational_overview ;;
    2|host) show_host_status ;;
    3|docker) show_docker_status ;;
    4|network|ports) show_network_status ;;
    5|agents) show_agents_zone ;;
    6|openclaw) show_openclaw_runtime_diagnostics ;;
    7|n8n) show_n8n_status ;;
    8|evidence) show_evidence_paths ;;
    9|back) return 1 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 2
      ;;
  esac
}

run_section() {
  case "$1" in
    1|overview|summary) show_operational_overview ;;
    2|openclaw) show_openclaw_status ;;
    3|broker|openclaw-broker) show_openclaw_capabilities ;;
    4|security|openclaw-security) show_security_presets_catalog ;;
    5|evidence) show_evidence_paths ;;
    6|diagnostics|openclaw-diagnostics) show_openclaw_runtime_diagnostics ;;
    7|help) show_help ;;
    host) show_host_status ;;
    docker) show_docker_status ;;
    n8n) show_n8n_status ;;
    network|ports) show_network_status ;;
    agents) show_agents_zone ;;
    openclaw-telegram) show_openclaw_telegram_runtime ;;
    openclaw-capabilities) show_openclaw_capabilities ;;
    openclaw-capabilities-audit) show_openclaw_capabilities_audit ;;
    openclaw-actions) show_openclaw_action_catalog ;;
    openclaw-logs) show_openclaw_logs ;;
    openclaw-health) show_openclaw_health ;;
    9|exit) exit 0 ;;
    *)
      echo "Opcion no valida: $1" >&2
      return 1
      ;;
  esac
}

init_console_style
init_menu_options

if [[ -n "${SECTION}" ]]; then
  run_section "${SECTION}"
  exit 0
fi

while true; do
  menu_choice_with_fallback "  [ MENÚ PRINCIPAL ]" MAIN_MENU_OPTIONS show_menu "Selecciona una opcion: " choice
  case "${choice}" in
    2)
      while true; do
        menu_choice_with_fallback "OpenClaw y Telegram" OPENCLAW_MENU_OPTIONS show_openclaw_menu "Selecciona una opcion: " openclaw_choice
        if ! run_openclaw_section "${openclaw_choice}"; then
          break
        fi
        pause_if_interactive
      done
      ;;
    3)
      while true; do
        menu_choice_with_fallback "Broker y capacidades" BROKER_MENU_OPTIONS show_broker_menu "Selecciona una opcion: " broker_choice
        if ! run_broker_section "${broker_choice}"; then
          break
        fi
        pause_if_interactive
      done
      ;;
    4)
      while true; do
        menu_choice_with_fallback "Seguridad y control" SECURITY_MENU_OPTIONS show_security_menu "Selecciona una opcion: " security_choice
        if ! run_security_section "${security_choice}"; then
          break
        fi
        pause_if_interactive
      done
      ;;
    6)
      while true; do
        menu_choice_with_fallback "Diagnostico" DIAGNOSTICS_MENU_OPTIONS show_diagnostics_menu "Selecciona una opcion: " diagnostics_choice
        if ! run_diagnostics_section "${diagnostics_choice}"; then
          break
        fi
        pause_if_interactive
      done
      ;;
    7)
      show_help
      pause_if_interactive
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
