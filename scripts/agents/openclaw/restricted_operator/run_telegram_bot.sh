#!/usr/bin/env bash
set -euo pipefail

POLICY_PATH="${1:-/opt/automation/agents/openclaw/broker/restricted_operator_policy.json}"
ENV_FILE="${TELEGRAM_BOT_ENV_FILE:-/etc/davlos/secrets/openclaw/telegram-bot.env}"
LOG_LEVEL="${TELEGRAM_BOT_LOG_LEVEL:-INFO}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -r "${ENV_FILE}" ]]; then
  echo "telegram env file not readable: ${ENV_FILE}" >&2
  exit 1
fi

if [[ ! -r "${POLICY_PATH}" ]]; then
  echo "telegram policy file not readable: ${POLICY_PATH}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

exec python3 "${SCRIPT_DIR}/telegram_bot.py" \
  --policy "${POLICY_PATH}" \
  --log-level "${LOG_LEVEL}"
