# OpenClaw Phase 3 Policy TTL MVP 2026-04-01

## objetivo

Evolucionar el broker restringido MVP hacia una política viva con TTL, `one_shot`, estado efectivo y utilidades mínimas de inspección, sin romper el modelo de seguridad actual.

## modelo aplicado

Se separan tres conceptos:

### política declarada

Versionada en JSON y usada como baseline:

- `enabled`
- `mode`
- `expires_at`
- `one_shot`
- `reason`
- `updated_by`

### runtime state

Store local pequeño y persistente para:

- consumo de acciones `one_shot`
- overrides runtime acotados
- persistencia del estado efectivo

### estado efectivo

Calculado por el broker en tiempo de ejecución combinando:

- política declarada
- runtime state
- tiempo actual

## cambios implementados

### broker

- validación de acciones por estado efectivo
- rechazo explícito de acciones:
  - deshabilitadas
  - expiradas
  - `one_shot` ya consumidas
- consumo automático de `one_shot` solo tras ejecución válida

### política

- soporte de:
  - `enabled`
  - `mode`
  - `expires_at`
  - `one_shot`
  - `reason`
  - `updated_by`
- validación estructural mínima
- helper para inspección de estado efectivo

### CLI

Se añadió utilidad mínima:

- `validate`
- `show`
- `show --at <timestamp>`
- `consume-one-shot`

### auditoría

Se añadieron eventos:

- `action_rejected_disabled`
- `action_rejected_expired`
- `action_rejected_consumed`
- `action_consumed_one_shot`
- `policy_validation_error`

## compatibilidad preservada

- handlers A/B/C/E siguen cerrados
- acción D sigue como stub seguro
- contrato HTTP base no cambia
- no se añadió shell arbitraria
- no se añadió Docker/systemd general

## archivos creados o modificados

### creados

- `docs/BROKER_POLICY_TTL_MVP.md`
- `docs/reports/OPENCLAW_PHASE_3_POLICY_TTL_MVP_2026-04-01.md`
- `scripts/agents/openclaw/restricted_operator/cli.py`

### modificados

- `scripts/agents/openclaw/restricted_operator/models.py`
- `scripts/agents/openclaw/restricted_operator/audit.py`
- `scripts/agents/openclaw/restricted_operator/policy.py`
- `scripts/agents/openclaw/restricted_operator/broker.py`
- `templates/openclaw/restricted_operator_policy.json`
- `tests/restricted_operator/test_broker.py`

## validación ejecutada

- `python3 -m unittest tests.restricted_operator.test_broker`
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy templates/openclaw/restricted_operator_policy.json validate`
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy templates/openclaw/restricted_operator_policy.json show --at 2026-04-02T00:00:00Z`

Resultado:

- 7 tests correctos
- política ejemplo válida
- inspección temporal del estado efectivo correcta

## riesgos residuales

- no hay identidad fuerte del caller
- no hay policy store distribuido ni TTL firmado
- no hay UI de activación/desactivación todavía
- el runtime state sigue siendo local al host
- la acción D sigue reservada y no ejecutable

## qué queda listo para Fase 4

- lectura de estado efectivo de capacidades
- activación/desactivación desde una UI externa futura
- visibilidad de expiración por acción
- consumo visible de capacidades `one_shot`
- base clara para que la consola DAVLOS abra/cierre capacidades sin tocar handlers

## decisión

### decisión

`GO` para Fase 4.

### motivo

El broker ya soporta política viva con expiración y `one_shot`, mantiene el modelo de acciones cerradas y deja preparada una base razonable para una capa de control de capacidades desde consola.
