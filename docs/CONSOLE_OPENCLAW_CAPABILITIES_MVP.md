# Console OpenClaw Capabilities MVP

## objetivo

Documentar el uso del submenú de capacidades OpenClaw en la DAVLOS VPN Console, reutilizando la CLI del broker y la política viva existentes.

## principio de integración

La consola no edita JSON directamente.

Toda operación se apoya en:

- `scripts/agents/openclaw/restricted_operator/cli.py`

La consola solo actúa como front-end Bash de operador para:

- listar estado efectivo
- habilitar o deshabilitar acciones
- habilitar una acción con TTL
- resetear una acción `one_shot`
- ver auditoría reciente

Las mutaciones no se aplican directamente desde Bash:

- la consola resuelve un `operator_id`
- la CLI valida ese `operator_id` contra la allowlist viva de operadores
- si el operador no está autorizado, la mutación se rechaza y queda auditada

## entrada al menú

Desde la consola:

- `7) OpenClaw / inference-gateway`
- `5) Capacidades OpenClaw`

También existen accesos directos:

- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-capabilities`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-capabilities-audit`

## operaciones disponibles

### ver acciones y estado efectivo

Muestra por acción:

- `action_id`
- `enabled`
- `mode`
- `expires_at`
- `one_shot`
- `one_shot_consumed`
- `status`
- `reason`
- `updated_by`

### habilitar acción

Pide:

- `operator_id` (explícito o derivado de la sesión)
- `action_id`
- `motivo`

Llama a:

- `cli.py enable`

### deshabilitar acción

Pide:

- `operator_id`
- `action_id`
- `motivo`

Llama a:

- `cli.py disable`

### habilitar acción con TTL

Pide:

- `operator_id`
- `action_id`
- `ttl_minutes`
- `motivo`

Llama a:

- `cli.py enable --ttl-minutes ...`

### resetear one-shot

Pide:

- `operator_id`
- `action_id`
- `motivo`

Llama a:

- `cli.py reset-one-shot`

### ver auditoría reciente

Llama a:

- `cli.py audit-tail --lines 20`

## trazabilidad mínima

Los cambios de capacidades dejan al menos:

- `action_id`
- tipo de cambio
- `reason`
- `operator_id`
- rol de operador si aplica
- operador efectivo (`updated_by`)

La auditoría se conserva en el audit log del broker.

## degradación segura

Si la sesión no tiene:

- acceso a la policy
- acceso a Python
- permisos para escribir el state store
- un `operator_id` autorizado para mutaciones

la consola:

- muestra un mensaje corto y claro
- no rompe otros menús
- no intenta editar JSON manualmente

## límites conocidos

- no existe autenticación fuerte final
- no hay menú final de producto, solo menú de operador
- el restart de OpenClaw sigue fuera del alcance de esta fase
- el menú opera sobre la policy disponible en runtime o, si no existe, sobre el ejemplo versionado visible
