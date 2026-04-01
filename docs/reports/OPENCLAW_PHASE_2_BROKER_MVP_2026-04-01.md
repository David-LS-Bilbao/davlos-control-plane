# OpenClaw Phase 2 Broker MVP 2026-04-01

## objetivo

Diseñar e implementar una primera base real de broker/restricted operator local para OpenClaw, con acciones cerradas, auditables y sin ejecución arbitraria.

## alcance ejecutado

- arquitectura MVP del broker local
- política base de acciones/permisos
- implementación inicial de acciones A/B/C/D/E
- auditoría mínima en JSONL
- pruebas unitarias básicas
- documentación de arquitectura y de fase

Fuera de alcance:

- integración con Telegram
- chat web final
- menú final de la consola
- policy store con TTL
- activación de acciones generales o shell arbitraria

## decisiones de diseño

### implementación

Se elige Python estándar con `http.server` y sin dependencias pesadas.

Razones:

- pequeño y auditable
- reversible
- suficiente para un broker local por loopback
- evita introducir frameworks o runtime adicional innecesario

### interfaz

- `GET /healthz`
- `POST /v1/actions/execute`

Modelo de llamada:

- `action_id`
- `params`
- `actor`

### política

La política vive en JSON y define:

- broker config
- catálogo de acciones
- checks de health permitidos
- streams de log permitidos
- targets de webhook permitidos
- límites de tail y escritura

### auditoría

Formato:

- JSON Lines

Campos mínimos:

- timestamp
- actor
- `action_id`
- parámetros saneados
- `ok`
- resultado
- error y `code` si aplica

## acciones implementadas

### Acción A

- ID: `action.health.general.v1`
- estado: implementada
- alcance:
  - ejecuta checks HTTP fijos definidos por política

### Acción B

- ID: `action.logs.read.v1`
- estado: implementada
- alcance:
  - lectura por `stream_id`
  - `tail_lines` acotado
  - sin rutas libres

### Acción C

- ID: `action.webhook.trigger.v1`
- estado: implementada
- alcance:
  - solo `target_id` permitido por política
  - payload mínimo controlado
  - sin URL libre

### Acción D

- ID: `action.openclaw.restart.v1`
- estado: stub seguro
- motivo:
  - no se fuerza restart por Docker/systemd general en esta fase
  - requiere wrapper root-owned o política sudo acotada

### Acción E

- ID: `action.dropzone.write.v1`
- estado: implementada
- alcance:
  - escritura solo en drop-zone controlada
  - sin path traversal
  - tamaño máximo configurado

## guardarraíles aplicados

- sin shell arbitraria
- sin comandos libres
- sin lectura de secretos
- sin acceso Docker general
- sin acceso systemd general
- sin rutas libres para logs
- sin filenames con traversal
- sin targets webhook libres
- validación explícita de tipos y rangos

## archivos creados o modificados

### creados

- `docs/BROKER_RESTRICTED_OPERATOR_MVP.md`
- `docs/reports/OPENCLAW_PHASE_2_BROKER_MVP_2026-04-01.md`
- `templates/openclaw/restricted_operator_policy.json`
- `scripts/agents/openclaw/restricted_operator/models.py`
- `scripts/agents/openclaw/restricted_operator/policy.py`
- `scripts/agents/openclaw/restricted_operator/audit.py`
- `scripts/agents/openclaw/restricted_operator/actions.py`
- `scripts/agents/openclaw/restricted_operator/broker.py`
- `scripts/agents/openclaw/restricted_operator/server.py`
- `tests/restricted_operator/test_broker.py`

## validación ejecutada

- `python3 -m unittest tests.restricted_operator.test_broker`
- `python3 scripts/agents/openclaw/restricted_operator/server.py --help`

Resultado:

- 5 tests correctos
- entrypoint CLI correcto

## riesgos residuales

- no hay autenticación fuerte del caller más allá del campo `actor`
- no hay policy store con TTL
- la acción D sigue en diseño y no en ejecución real
- el target de webhook controlado sigue siendo un contrato base, no integración final de producto
- falta integración del runtime real de OpenClaw con este broker

## qué queda listo para Fase 3

- broker local mínimo ya implementado
- catálogo inicial de acciones por ID
- política base separada del código
- auditoría mínima funcional
- superficie controlada para introducir policy store con TTL

## decisión

### decisión

`GO` para Fase 3.

### motivo

Ya existe una base real de broker restringido donde OpenClaw puede pedir acciones por ID bajo validación, política y auditoría, sin depender de acceso libre ni de ejecución arbitraria.
