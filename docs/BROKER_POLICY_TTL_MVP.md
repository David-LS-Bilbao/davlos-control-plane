# Broker Policy TTL MVP

## objetivo

Extender el broker restringido de OpenClaw con una política viva que soporte expiración, `one_shot` y estado efectivo de capacidades sin romper el modelo de seguridad actual.

## modelo elegido

Se separan dos capas:

### política declarada

Vive en el JSON de política versionado y define el baseline deseado por acción:

- `enabled`
- `mode`
- `expires_at`
- `one_shot`
- `reason`
- `updated_by`
- `permission`
- `description`

### estado runtime

Vive en un state store local separado y pequeño.

Uso:

- consumo de acciones `one_shot`
- overrides runtime acotados
- persistencia de estado efectivo entre ejecuciones

## estado efectivo

El broker calcula el estado efectivo en runtime combinando:

1. política declarada
2. runtime state
3. tiempo actual

Reglas:

- si `enabled=false`, la acción queda `disabled`
- si `expires_at <= now`, la acción queda `expired`
- si `one_shot=true` y ya fue consumida, la acción queda `consumed`
- en cualquier otro caso la acción queda `enabled`

## modos

### `readonly`

Acciones de lectura o inspección con radio de impacto nulo o muy bajo.

### `restricted`

Acciones cerradas con efecto controlado, pero que no deben abrir shell ni ejecución general.

## ciclo de vida de una acción

### habilitada

- puede ejecutarse si el handler existe y la validación de parámetros pasa

### deshabilitada

- se rechaza con `action_rejected_disabled`

### expirada

- se rechaza con `action_rejected_expired`

### one-shot consumida

- tras una ejecución válida se marca en el state store
- el broker emite `action_consumed_one_shot`
- siguientes intentos se rechazan como consumidos

## utilidades CLI mínimas

### validar política

```bash
python3 scripts/agents/openclaw/restricted_operator/cli.py \
  --policy templates/openclaw/restricted_operator_policy.json \
  validate
```

### ver estado efectivo actual

```bash
python3 scripts/agents/openclaw/restricted_operator/cli.py \
  --policy templates/openclaw/restricted_operator_policy.json \
  show
```

### simular expiración o estado a un instante dado

```bash
python3 scripts/agents/openclaw/restricted_operator/cli.py \
  --policy templates/openclaw/restricted_operator_policy.json \
  show \
  --at 2026-04-02T00:00:00Z
```

### marcar una acción one-shot como consumida

```bash
python3 scripts/agents/openclaw/restricted_operator/cli.py \
  --policy templates/openclaw/restricted_operator_policy.json \
  consume-one-shot \
  --action-id action.webhook.trigger.v1 \
  --updated-by operator
```

## auditoría de eventos de política

Eventos relevantes:

- `action_rejected_disabled`
- `action_rejected_expired`
- `action_rejected_consumed`
- `action_consumed_one_shot`
- `policy_validation_error`

## compatibilidad

- los handlers existentes A/B/C/E siguen cerrados
- la acción D sigue siendo stub seguro
- el contrato HTTP base no cambia

## límites conocidos

- no existe todavía policy store con TTL distribuido
- no existe identidad fuerte del caller
- no existe UI de activación/desactivación todavía

## preparado para Fase 4

La consola DAVLOS ya podrá:

- leer estado efectivo
- mostrar expiraciones
- consumir o agotar acciones `one_shot`
- preparar una capa de activación/desactivación sin tocar handlers
