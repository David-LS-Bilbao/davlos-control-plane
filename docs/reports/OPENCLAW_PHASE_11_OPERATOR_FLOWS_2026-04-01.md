# OPENCLAW Phase 11 Operator Flows

Fecha: 2026-04-01  
Rama: `codex/openclaw-console-readonly`

## Objetivo

Validar flujos operativos reales de operador usando las piezas ya construidas, antes de abrir nuevos canales o añadir más complejidad.

## Flujos Probados

### Flujo 1: observabilidad diaria

Comprobación:
- `bash scripts/console/davlos-vpn-console.sh openclaw-capabilities`

Resultado:
- correcto
- la salida es legible para operador
- el estado efectivo de capacidades se entiende rápido

### Flujo 2: habilitar una capacidad con TTL

Comprobación:
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy /tmp/openclaw_operator_flows/policy.json enable --action-id action.dropzone.write.v1 --ttl-minutes 30 --operator-id davlos-operator --reason phase11_ttl_flow`
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy /tmp/openclaw_operator_flows/policy.json show --format console`

Resultado:
- correcto
- el estado muestra `expires_at` de forma clara

### Flujo 3: consumir y resetear one-shot

Comprobación:
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy /tmp/openclaw_operator_flows/policy.json consume-one-shot --action-id action.webhook.trigger.v1 --operator-id root --reason phase11_consume`
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy /tmp/openclaw_operator_flows/policy.json reset-one-shot --action-id action.webhook.trigger.v1 --operator-id root --reason phase11_reset`

Resultado:
- correcto
- el flujo es válido cuando policy y runtime state pertenecen al mismo contexto

### Flujo 4: ejecución permitida por Telegram

Comprobación simulada:
- `/status`
- `/execute action.logs.read.v1 stream_id=openclaw_runtime tail_lines=2`
- `/audit_tail`

Resultado:
- correcto
- el canal Telegram ya es útil para consulta rápida y ejecución cerrada

### Flujo 5: revisión de auditoría

Comprobación:
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy /tmp/openclaw_operator_flows/policy.json audit-tail --lines 12 --format console`

Resultado:
- correcto
- la salida es suficiente para MVP
- deja ver mutaciones, ejecución Telegram y eventos one-shot

## Fricciones Principales

### 1. Policy declarada vs runtime state

La fricción principal no es un fallo del broker sino de modelo operativo: la policy del repo representa contrato, mientras que el runtime state refleja consumo, TTL y auditoría real. Si el operador mezcla ambos niveles, puede interpretar mal el estado.

### 2. Auditoría de plantilla

La plantilla versionada puede mostrar auditoría vacía aunque el sistema real esté funcionando. Para validar trazabilidad real hay que mirar el audit log del runtime activo o usar una policy temporal con state store propio.

### 3. Ergonomía de Telegram

Telegram ya es útil, pero su sintaxis `k=v` sigue siendo austera. Hoy vale para acciones pequeñas y cerradas; no justifica por sí sola abrir un chat web.

## Microajustes Aplicados

Ninguno.

Durante la fase apareció una inconsistencia puntual al probar `one_shot`, pero no fue reproducible al repetir el flujo con policy/runtime coherentes. No se justificó tocar código en esta fase.

## Validaciones Ejecutadas

- `bash -n scripts/console/davlos-vpn-console.sh`
- `python3 -m unittest tests.restricted_operator.test_broker`
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy templates/openclaw/restricted_operator_policy.json validate`
- validaciones operativas sobre `/tmp/openclaw_operator_flows/policy.json`

## Resultado

La base actual es suficientemente sólida para operación MVP real.

Conclusión recomendada:

- seguir con DAVLOS VPN Console como herramienta principal
- mantener Telegram como canal ligero y cerrado
- no abrir chat web todavía
- priorizar, si hace falta más inversión, una acción nueva y concreta de broker o una mejora pequeña de visibilidad del runtime activo

## Estado Final

La fase cumple su objetivo: ofrece base objetiva para decidir la siguiente inversión de esfuerzo sin añadir complejidad prematura.
