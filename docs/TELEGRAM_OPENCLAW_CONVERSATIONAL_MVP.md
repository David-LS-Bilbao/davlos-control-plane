# Telegram OpenClaw Conversational MVP

## objetivo

Añadir una capa conversacional pequeña y controlada sobre el bot Telegram existente, sin convertirlo en un chatbot libre ni alterar el modelo de seguridad actual.

## principios

- Telegram sigue siendo solo canal
- la autorización real sigue en `operator_auth`
- la policy viva sigue siendo la fuente de verdad
- la ejecución real sigue en el broker restringido o en las mutaciones controladas ya existentes de policy
- no hay shell arbitraria
- no hay texto libre convertido en comandos abiertos

## enfoque elegido

Se usa un intérprete de intención cerrado por reglas:

- matching simple
- frases soportadas explícitas
- alias mínimos
- confirmación obligatoria para mutaciones

No se introduce LLM externa ni dependencias nuevas.

## intenciones soportadas en esta fase

### lectura

- estado general
- capacidades activas
- auditoría reciente
- logs permitidos

### mutación con confirmación

- habilitar capacidad
- deshabilitar capacidad
- habilitar capacidad con TTL en minutos
- resetear one-shot

## frases soportadas

Ejemplos de lectura:

- `estado general`
- `como va`
- `capacidades activas`
- `que capacidades hay`
- `auditoria reciente`
- `logs openclaw`
- `logs openclaw 20`
- `logs auditoria`

Ejemplos de mutación:

- `habilita action.dropzone.write.v1`
- `deshabilita action.dropzone.write.v1`
- `habilita action.dropzone.write.v1 por 15 minutos`
- `resetea one-shot action.webhook.trigger.v1`

Alias mínimos:

- `dropzone` -> `action.dropzone.write.v1`
- `webhook` -> `action.webhook.trigger.v1`
- `restart` -> `action.openclaw.restart.v1`

## confirmación

Las mutaciones no ejecutan en el primer mensaje.

Flujo:

1. el bot detecta una intención mutante
2. construye una acción interpretada
3. responde con un resumen
4. pide confirmación explícita
5. solo ejecuta si el usuario responde afirmativamente

Confirmaciones aceptadas:

- `si`
- `sí`
- `confirmar`
- `confirmo`
- `ok`
- `dale`

Cancelaciones:

- `no`
- `cancelar`
- `cancela`
- `rechazar`

## auditoría añadida

Para modo conversacional se registran:

- `intent_detected`
- `confirmation_requested`
- `confirmation_accepted`
- `confirmation_rejected`
- `action_executed`
- `action_failed`
- `intent_rejected_unsupported`

Los slash commands existentes se mantienen con su auditoría previa.

## seguridad

### mantenido

- allowlist por chat/user
- resolución a `operator_id`
- autorización por permisos en policy
- uso del broker para acciones de ejecución
- rechazo de intents no soportadas o ambiguas

### no permitido

- shell arbitraria
- JSON libre
- prompts abiertos
- confirmación implícita
- ejecución mutante sin confirmación

## compatibilidad

Los slash commands actuales siguen funcionando:

- `/help`
- `/status`
- `/capabilities`
- `/audit_tail`
- `/execute <action_id> [k=v ...]`

## límites

- parser deliberadamente pequeño
- comprensión limitada a frases soportadas
- confirmación pendiente en memoria del proceso
- no hay NLU avanzada ni aprendizaje

## siguiente fase razonable

- ampliar el catálogo de frases seguras
- mejorar mensajes de ayuda y confirmación
- persistir confirmaciones pendientes si llegara a hacer falta
