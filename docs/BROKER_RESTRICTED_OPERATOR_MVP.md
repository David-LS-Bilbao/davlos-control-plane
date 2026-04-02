# Broker Restricted Operator MVP

## objetivo

Definir una primera base real de broker local para acciones restringidas de OpenClaw, sin shell arbitraria y sin acoplar todavía la solución a Telegram, chat web o menú final de consola.

## arquitectura elegida

Se elige un broker local pequeño en Python estándar con estas piezas:

- endpoint HTTP local por loopback
- política declarativa en JSON
- registro cerrado de `action_id`
- handlers explícitos por acción
- auditoría mínima en JSONL

Flujo:

1. OpenClaw o un cliente local envía `POST /v1/actions/execute`
2. el broker valida `action_id`
3. valida que la acción esté habilitada por política
4. valida parámetros según el handler
5. ejecuta solo lógica cerrada y auditada
6. devuelve resultado estructurado

## principios de seguridad

- no se ejecuta shell arbitraria
- no se aceptan comandos libres
- no hay acceso Docker general
- no hay acceso systemd general
- no se leen secretos
- no se aceptan rutas libres para logs ni escritura
- toda acción usa IDs estables y validación explícita de parámetros

## árbol de archivos

- `scripts/agents/openclaw/restricted_operator/server.py`
- `scripts/agents/openclaw/restricted_operator/broker.py`
- `scripts/agents/openclaw/restricted_operator/actions.py`
- `scripts/agents/openclaw/restricted_operator/policy.py`
- `scripts/agents/openclaw/restricted_operator/audit.py`
- `scripts/agents/openclaw/restricted_operator/models.py`
- `templates/openclaw/restricted_operator_policy.json`
- `tests/restricted_operator/test_broker.py`

## API mínima

### health del broker

- `GET /healthz`

### ejecución de acciones

- `POST /v1/actions/execute`

Payload mínimo:

```json
{
  "action_id": "action.health.general.v1",
  "params": {},
  "actor": "openclaw"
}
```

## acciones MVP

### Acción A

- ID: `action.health.general.v1`
- sin parámetros
- ejecuta checks HTTP fijos definidos por política

### Acción B

- ID: `action.logs.read.v1`
- parámetros:
  - `stream_id`
  - `tail_lines`
- solo permite leer streams predeclarados por `stream_id`

### Acción C

- ID: `action.webhook.trigger.v1`
- parámetros:
  - `target_id`
  - `event_type`
  - `note`
- solo dispara targets fijos definidos por política

### Acción D

- ID: `action.openclaw.restart.v1`
- reservada
- no habilitada en el MVP
- requiere wrapper root-owned o política sudo acotada en una fase posterior

### Acción E

- ID: `action.dropzone.write.v1`
- parámetros:
  - `filename`
  - `content`
- solo escribe en una drop-zone fija
- sin path traversal

## auditoría mínima

Cada ejecución registra:

- timestamp
- actor
- `action_id`
- parámetros no sensibles o saneados
- resultado
- error y código si aplica

Formato:

- JSON Lines

## política base

La política base vive en:

- `templates/openclaw/restricted_operator_policy.json`

Contiene:

- bind del broker
- ruta de auditoría
- drop-zone
- catálogo de acciones
- checks de health permitidos
- streams de log permitidos
- targets de webhook permitidos

## límites conocidos

- no hay policy store con TTL
- no hay identidad fuerte más allá del campo `actor`
- no hay integración directa aún en el runtime de OpenClaw
- la acción de restart queda en stub seguro por ahora

## siguiente evolución natural

### Fase 3

- policy store con TTL
- activación temporal de acciones
- contexto de autorización más estricto

### Fase 4

- integración con menú/control plane
- integración con clientes conversacionales
