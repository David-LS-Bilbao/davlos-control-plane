#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECTION="${1:-}"

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
    "${REPO_ROOT}/docs/MVP_PHASE_8_RESTRICTED_OPERATOR.md"
  echo
  echo "-- ultimos ficheros de evidencia --"
  find "${REPO_ROOT}/evidence" -maxdepth 3 -type f -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort | tail -n 12
}

show_help() {
  print_header
  echo "[Ayuda / limites del MVP]"
  echo
  cat <<'EOF'
- Esta consola es readonly.
- No reinicia servicios, no toca secretos y no modifica producción.
- Si una comprobación requiere Docker o sudo y no está disponible, muestra un aviso y sigue.
- La fuente de verdad operativa actual está en README.md y evidence/.
- El inventario funcional mínimo de workflows de n8n sigue en estado PARTIAL por acceso readonly limitado al runtime activo.
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
6) Ayuda / limites del MVP
9) Salir
EOF
}

run_section() {
  case "$1" in
    1|host) show_host_status ;;
    2|docker) show_docker_status ;;
    3|n8n) show_n8n_status ;;
    4|network|ports) show_network_status ;;
    5|evidence) show_evidence_paths ;;
    6|help) show_help ;;
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
