#!/usr/bin/env bash
set -euo pipefail

# Precheck readonly de coherencia del repo para OpenClaw.
# Este script NO valida el host, NO inspecciona runtime vivo y NO muta nada.
# Su único objetivo es detectar drift documental/material dentro del propio repo
# antes de plantear un redeploy o una intervención posterior.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

README_ROOT="${REPO_ROOT}/README.md"
DOCS_AGENTS="${REPO_ROOT}/docs/AGENTS.md"
SCRIPT_README="${SCRIPT_DIR}/README.md"
HELPER_DOC="${REPO_ROOT}/docs/OPENCLAW_READONLY_HELPER_INSTALL.md"
DRIFT_DOC="${REPO_ROOT}/docs/OPENCLAW_RUNTIME_DRIFT_2026-04-08.md"
DEPLOY_SCRIPT="${SCRIPT_DIR}/30_first_local_deploy.sh"

failures=0

print_check() {
  local status="$1"
  local message="$2"
  printf '%s %s\n' "${status}" "${message}"
}

fail() {
  local message="$1"
  print_check "FAIL" "${message}"
  failures=$((failures + 1))
}

pass() {
  local message="$1"
  print_check "OK  " "${message}"
}

check_file() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    pass "archivo presente: ${path}"
  else
    fail "archivo ausente: ${path}"
  fi
}

echo "== openclaw repo drift readonly precheck =="
echo "scope=repo_only"
echo "repo_root=${REPO_ROOT}"

check_file "${README_ROOT}"
check_file "${DOCS_AGENTS}"
check_file "${SCRIPT_README}"
check_file "${HELPER_DOC}"
check_file "${DRIFT_DOC}"
check_file "${DEPLOY_SCRIPT}"

if rg -q '30_first_local_deploy\.sh' "${SCRIPT_README}" && \
   rg -q 'deploy real|despliega `openclaw-gateway`|impacto potencial sobre runtime vivo' "${SCRIPT_README}"; then
  pass "scripts/agents/openclaw/README.md distingue staging/prechecks de deploy real"
else
  fail "scripts/agents/openclaw/README.md no deja suficientemente claro que 30_first_local_deploy.sh es deploy real"
fi

if rg -q 'broker restringido operativo|Telegram persistente operativo|helper readonly' "${README_ROOT}" && \
   rg -q 'broker restringido operativo|Telegram persistente operativo|helper readonly' "${DOCS_AGENTS}"; then
  pass "README.md y docs/AGENTS.md alinean broker, Telegram y helper como parte del runtime observado"
else
  fail "docs/AGENTS.md y README.md principal siguen desalineados sobre broker, Telegram o helper readonly"
fi

if rg -q 'operational_logs_recent' "${HELPER_DOC}" && \
   rg -q 'operational_logs_recent' "${REPO_ROOT}/templates/openclaw/davlos-openclaw-readonly.sh"; then
  pass "la documentación del helper refleja el quinto modo operational_logs_recent"
else
  fail "la documentación del helper no refleja operational_logs_recent como quinto modo"
fi

if rg -q 'bind: "lan"|loopback-only|drift contractual' "${DRIFT_DOC}"; then
  pass "el documento de drift recoge el gap loopback-only vs bind: lan"
else
  fail "el documento de drift no recoge claramente el gap loopback-only vs bind: lan"
fi

if rg -q 'ownership mixto|root.*compose.*broker.*dropzone.*secretos|devops.*config.*state.*logs' "${README_ROOT}" && \
   rg -q 'ownership observado del runtime' "${DOCS_AGENTS}"; then
  pass "la documentación crítica ya deja explícito el ownership mixto observado"
else
  fail "la documentación crítica no deja suficientemente claro el ownership mixto observado"
fi

echo "summary_failures=${failures}"

if (( failures > 0 )); then
  echo "resultado=DRIFT_MATERIAL_DETECTADO"
  exit 1
fi

echo "resultado=REPO_COHERENCIA_MINIMA_OK"
