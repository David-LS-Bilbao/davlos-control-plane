# Telegram OpenClaw Wake Mode MVP

## objetivo

Añadir un modo `wake/sleep` al canal Telegram de OpenClaw para permitir una conversación más natural sin convertir el bot en un agente libre.

## principios

- Telegram sigue siendo solo canal.
- La identidad real sigue resolviéndose por allowlist Telegram -> `operator_id`.
- La autorización real sigue en `operator_auth`.
- La ejecución real sigue en broker restringido o en mutaciones controladas de policy.
- No se introduce shell arbitraria.

## modelo de sesión

Cada sesión se indexa por `chat_id:user_id`.

Estado en memoria:

- `assistant_wake`
- `assistant_sleep`
- `last_activity_at`
- `operator_id`
- confirmación pendiente por chat/user

Timeout por inactividad:

- default `300s`
- configurable por env `OPENCLAW_TELEGRAM_ASSISTANT_IDLE_TIMEOUT_SECONDS`
- al expirar, se cierra la sesión y se limpia cualquier confirmación pendiente

## comandos

- `/wake`: activa modo asistente
- `/sleep`: sale del modo asistente
- slash commands actuales se mantienen:
  - `/help`
  - `/status`
  - `/capabilities`
  - `/audit_tail`
  - `/execute <action_id> [k=v ...]`

Equivalentes naturales mínimos:

- `despierta`
- `despierta openclaw`
- `duerme`
- `duermete`

## conversación soportada

Fuera de `wake`:

- sigue activo el modo conversacional cerrado de la fase anterior
- frases estrictas y seguras

En `wake`:

- estado general
- capacidades activas
- auditoría reciente
- logs permitidos
- explicación del estado
- propuesta de acción

Ejemplos:

- `como estamos`
- `que puedes hacer`
- `que ha pasado`
- `logs openclaw 20`
- `explica el estado`
- `que propones`

## mutaciones

Las mutaciones siguen flujo controlado:

1. detectar intención
2. comprobar autorización de mutación frente a policy
3. proponer acción concreta
4. pedir confirmación
5. ejecutar solo tras confirmación explícita

Confirmaciones aceptadas:

- `si`
- `sí`
- `confirmar`
- `confirmo`
- `ok`
- `dale`

Confirmaciones negativas:

- `no`
- `cancelar`
- `cancela`
- `rechazar`

## auditoría

Eventos relevantes:

- `assistant_wake`
- `assistant_sleep`
- `intent_detected`
- `intent_rejected_unsupported`
- `intent_rejected_unauthorized`
- `response_generated`
- `confirmation_requested`
- `confirmation_accepted`
- `confirmation_rejected`
- `action_executed`
- `action_failed`

## límites

- la sesión vive en memoria del proceso
- no hay memoria larga
- el parser sigue siendo cerrado por reglas
- no existe ejecución libre ni prompts abiertos contra shell
- las propuestas son textuales; la ejecución real sigue separada
