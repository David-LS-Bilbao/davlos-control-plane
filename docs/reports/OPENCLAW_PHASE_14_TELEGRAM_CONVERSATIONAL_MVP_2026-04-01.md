# OPENCLAW Phase 14 Telegram Conversational MVP

Fecha: 2026-04-01  
Rama: `codex/openclaw-console-readonly`

## objetivo

Añadir una primera capa conversacional controlada sobre el bot Telegram de OpenClaw, manteniendo slash commands, seguridad actual y confirmación explícita para mutaciones.

## diseño aplicado

Se eligió un modelo cerrado y pequeño:

- parser por reglas
- matching de frases soportadas
- alias mínimos
- confirmación en memoria para mutaciones

No se añadió:

- LLM externa
- shell arbitraria
- chat libre
- nuevas capacidades del broker

## intenciones soportadas

### lectura

- estado general
- capacidades activas
- auditoría reciente
- logs permitidos

### mutación con confirmación

- habilitar capacidad
- deshabilitar capacidad
- habilitar con TTL
- resetear one-shot

## integración

La integración se hizo sobre `telegram_bot.py` sin rehacer el bot:

- los slash commands se mantienen intactos
- los mensajes no slash pasan por el intérprete conversacional
- si la intención es readonly, se reutilizan handlers existentes o una acción cerrada del broker
- si la intención es mutante, se pide confirmación antes de ejecutar

## seguridad

Se mantiene:

- allowlist por chat/user
- resolución a `operator_id`
- autorización por policy
- broker para ejecución de acciones
- mutaciones solo a través de funciones ya existentes de policy con auth explícita
- rechazo de frases ambiguas o no soportadas

## auditoría añadida

Eventos nuevos:

- `intent_detected`
- `confirmation_requested`
- `confirmation_accepted`
- `confirmation_rejected`
- `action_executed`
- `action_failed`
- `intent_rejected_unsupported`

## validaciones ejecutadas

```bash
python3 -m unittest tests.restricted_operator.test_broker
```

## tests añadidos

- intención conversacional de estado
- intención conversacional de capacidades
- intención mutante que requiere confirmación
- mutación conversacional ejecutada tras confirmación
- rechazo de intención no soportada

La suite quedó en:

- `Ran 32 tests`
- `OK`

## archivos tocados

- `scripts/agents/openclaw/restricted_operator/telegram_bot.py`
- `tests/restricted_operator/test_broker.py`
- `docs/TELEGRAM_OPENCLAW_CONVERSATIONAL_MVP.md`

## riesgos residuales

- el parser sigue siendo deliberadamente estrecho
- la confirmación pendiente vive en memoria del proceso
- la cobertura de lenguaje natural es limitada y conservadora
- las mutaciones conversacionales reutilizan funciones de policy existentes en vez de introducir un plano nuevo

## conclusión

Telegram deja de ser solo slash commands y gana conversación útil, pero sigue sin haber ejecución arbitraria. El modelo de seguridad actual se mantiene y las mutaciones requieren confirmación explícita.
