# Console OpenClaw Capabilities MVP

## objetivo

Documentar el uso del bloque `Broker y capacidades` de la DAVLOS VPN Console, reutilizando la CLI del broker, la policy viva y el helper readonly host-side cuando el runtime no es legible directamente.

## principio de integración

La consola no edita JSON directamente.

Toda mutación se apoya en:

- `scripts/agents/openclaw/restricted_operator/cli.py`

La consola actúa como front-end Bash de operador para:

- listar estado efectivo
- ver auditoría reciente
- ver catálogo de acciones
- habilitar o deshabilitar acciones
- habilitar una acción con TTL
- resetear una acción `one_shot`

Las mutaciones no se aplican directamente desde Bash:

- la consola resuelve un `operator_id`
- la CLI valida ese `operator_id` contra la allowlist viva de operadores
- si el operador no está autorizado, la mutación se rechaza y queda auditada

La consola prioriza la lectura directa del runtime.

Si la lectura falla por permisos y el helper readonly está disponible, puede usar:

- `sudo -n /usr/local/sbin/davlos-openclaw-readonly`

Si la vista no puede leer runtime ni vía sesión ni vía helper, degrada a información declarativa del repo cuando esa vista lo permite.

## entrada al menú

Desde la consola:

- `3) Broker y capacidades`
- `1) Estado efectivo`
- `2) Auditoría reciente`
- `3) Catálogo de acciones`
- `4) Control manual por acción`
- `5) Diagnóstico broker/runtime`

También existen accesos directos:

- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-capabilities`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-capabilities-audit`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-actions`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-diagnostics`

## operaciones disponibles

### ver acciones y estado efectivo

Muestra por acción:

- `status`
- `mode`
- `allowed`
- `permission`
- `action_id`
- `expires_at`
- `one_shot`
- `consumed`
- `reason`

`updated_by` sigue existiendo en runtime y auditoría, pero la salida `console` no lo imprime hoy.

Cuando el runtime no es legible directamente pero el helper readonly está instalado, la consola usa:

- `sudo -n /usr/local/sbin/davlos-openclaw-readonly broker_state_console`

### ver auditoría reciente

Llama a:

- `cli.py audit-tail --lines 20`

Si la CLI no puede leer el runtime por permisos y el helper readonly está instalado, la consola usa:

- `sudo -n /usr/local/sbin/davlos-openclaw-readonly broker_audit_recent`

### ver catálogo de acciones

La consola muestra una ficha operativa por acción conocida con:

- `label`
- `action_id`
- `permission`
- descripción corta
- badge visual `READONLY`, `RESTRICTED` o `CONTROL`

### diagnóstico broker/runtime

El bloque de diagnóstico puede combinar:

- lectura directa de runtime y servicios visibles desde la sesión
- `sudo -n /usr/local/sbin/davlos-openclaw-readonly operational_logs_recent`

`operational_logs_recent` mantiene superficie cerrada:

- solo expone las últimas líneas de una allowlist fija de units
- no acepta nombres de unit arbitrarios
- no equivale a acceso general a `journald`

La allowlist actual cubre:

- `openclaw-telegram-bot.service`
- `inference-gateway.service`
- `obsidian-vault-backup.service`
- `obsidian-vault-restore-check.service`
- `openclaw-boundary-backup.service`

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

### control manual por acción

En modo interactivo, la consola ya no obliga al operador a memorizar siempre `action_id`.

Puede seleccionar desde menú:

- `action.webhook.trigger.v1`
- `action.dropzone.write.v1`
- `action.openclaw.restart.v1`

o introducir un `action_id` manual cuando haga falta.

## trazabilidad mínima

Los cambios de capacidades dejan al menos:

- `action_id`
- tipo de cambio
- `reason`
- `operator_id`
- rol de operador si aplica
- operador efectivo (`updated_by`)

La auditoría se conserva en el audit log del broker.

Cuando existe helper readonly, la consola puede leer esa auditoría y el estado efectivo sin abrir permisos generales sobre `/opt/automation`.

La vista `console` no expone todos los campos internos del runtime; `updated_by` sigue siendo trazable en runtime y auditoría aunque no se renderice en esa salida.

## degradación segura

Si la sesión no tiene:

- acceso a la policy
- acceso a Python
- permisos para leer o escribir el state store
- un `operator_id` autorizado para mutaciones

la consola:

- muestra un mensaje corto y claro
- no rompe otros menús
- no intenta editar JSON manualmente
- si la lectura runtime falla por permisos y existe helper readonly, intenta leer runtime y auditoría por esa vía antes de degradar

## límites conocidos

- no existe autenticación fuerte final
- no hay UI web final de control; la operación sigue siendo consola + Telegram
- `action.openclaw.restart.v1` sigue siendo la acción más sensible y debe abrirse con TTL corto
- sin helper readonly o permisos equivalentes, la visibilidad del runtime activo puede degradarse
- el menú prioriza siempre policy/runtime real; el ejemplo versionado del repo solo es fallback declarativo
