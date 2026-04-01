# Telegram OpenClaw MVP

## objetivo

Añadir un canal Telegram privado y pequeño para OpenClaw sin romper el boundary actual:

- Telegram solo transporta comandos y respuestas
- la autorización real sigue en la policy/operator auth
- la ejecución real sigue en el broker restringido

## arquitectura

Flujo:

1. Telegram recibe un mensaje privado.
2. `telegram_bot.py` resuelve `chat_id` o `user_id` contra la allowlist local.
3. El adaptador obtiene el `operator_id` asociado.
4. La autorización se valida contra `operator_auth`.
5. Si el comando es `/execute`, la ejecución pasa por `RestrictedOperatorBroker`.
6. La respuesta se devuelve a Telegram y queda auditada.

## ficheros

- `scripts/agents/openclaw/restricted_operator/telegram_bot.py`
- `templates/openclaw/restricted_operator_policy.json`
- `templates/openclaw/telegram-bot.env.example`

## policy

La configuración Telegram vive en el bloque `telegram` de la policy:

- `enabled`
- `bot_token_env`
- `api_base_url`
- `poll_timeout_seconds`
- `audit_tail_lines`
- `offset_store_path`
- `allowed_chats`
- `allowed_users`

Cada chat o usuario permitido se mapea a un `operator_id` local.

## comandos soportados

- `/help`
- `/status`
- `/capabilities`
- `/audit_tail`
- `/execute <action_id> [k=v ...]`

## execute

`/execute` usa parsing cerrado por acción.

Acciones soportadas en el adaptador:

- `action.health.general.v1`
- `action.logs.read.v1 stream_id=<id> [tail_lines=<n>]`
- `action.webhook.trigger.v1 target_id=<id> event_type=<id> note=<texto_url_encoded>`
- `action.openclaw.restart.v1`
- `action.dropzone.write.v1 filename=<basename> content=<texto_url_encoded>`

No se acepta JSON libre ni shell arbitraria.

## autorización

Reglas:

- chat o user deben estar allowlisted
- el `operator_id` resuelto debe existir y estar habilitado
- para `/status`, `/capabilities` y `/audit_tail` se exige `policy.read`
- para `/execute` se exige el permiso específico declarado por la acción

## auditoría

El canal Telegram deja eventos útiles en el audit log del broker:

- `telegram_command_executed`
- `telegram_command_rejected_unauthorized_chat`
- `telegram_command_rejected_operator_not_authorized`
- `telegram_command_rejected_invalid_params`
- `telegram_command_rejected_unknown_action`
- `telegram_action_requested`

Campos relevantes:

- `operator_id`
- `telegram_chat_id`
- `telegram_user_id`
- `action_id`
- `command`
- `ok`

## despliegue mínimo

1. Copiar la policy viva y ajustar el bloque `telegram`.
2. Sustituir `allowed_chats` y/o `allowed_users` por IDs reales privados.
3. Exportar `OPENCLAW_TELEGRAM_BOT_TOKEN` desde un fichero root-owned fuera del repo.
4. Arrancar:

```bash
python3 /opt/control-plane/scripts/agents/openclaw/restricted_operator/telegram_bot.py \
  --policy /opt/automation/agents/openclaw/broker/restricted_operator_policy.json
```

## límites

- sin chat web
- sin autenticación remota fuerte
- sin menús conversacionales complejos
- polling simple, no webhook público
