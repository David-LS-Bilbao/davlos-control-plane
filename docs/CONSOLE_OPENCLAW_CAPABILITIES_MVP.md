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

- `action_id`
- `motivo`

Llama a:

- `cli.py enable`

### deshabilitar acción

Pide:

- `action_id`
- `motivo`

Llama a:

- `cli.py disable`

### habilitar acción con TTL

Pide:

- `action_id`
- `ttl_minutes`
- `motivo`

Llama a:

- `cli.py enable --ttl-minutes ...`

### resetear one-shot

Pide:

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
- operador (`updated_by`)

La auditoría se conserva en el audit log del broker.

## degradación segura

Si la sesión no tiene:

- acceso a la policy
- acceso a Python
- permisos para escribir el state store

la consola:

- muestra un mensaje corto y claro
- no rompe otros menús
- no intenta editar JSON manualmente

## límites conocidos

- no existe autenticación fuerte final
- no hay menú final de producto, solo menú de operador
- el restart de OpenClaw sigue fuera del alcance de esta fase
- el menú opera sobre la policy disponible en runtime o, si no existe, sobre el ejemplo versionado visible
