# OpenClaw Baseline Prudente Validado 2026-04-08

## propósito

Dejar constancia formal de que el boundary OpenClaw ya puede tratarse como `baseline prudente validado` a partir de validación host-side estrictamente readonly.

## alcance

Esta decisión cubre solo:

- runtime state del restricted operator
- lockfile asociado
- helper readonly instalado
- sudoers del helper
- verificación funcional mínima de los modos readonly expuestos

No cierra otros frentes operativos del boundary ni sustituye futuras validaciones host-side acotadas.

## decisión final

`baseline prudente validado`

## hechos confirmados en host

- `/opt/automation/agents/openclaw/broker/state/restricted_operator_state.json` existe y es `root:root` `0600`
- `/opt/automation/agents/openclaw/broker/state/restricted_operator_state.json.lock` existe y es `root:root` `0600`
- `/opt/automation/agents/openclaw/broker/state` es `root:root` `0750`
- `/etc/systemd/system/openclaw-telegram-bot.service` corre como `User=root`, `Group=root`
- `openclaw-gateway` corre como `node` y no monta `broker/state`
- `/usr/local/sbin/davlos-openclaw-readonly` es `root:root` `0750`
- `/etc/sudoers.d/davlos-openclaw-readonly` es `root:root` `0440`
- el helper instalado soporta 5 modos:
  - `runtime_summary`
  - `broker_state_console`
  - `broker_audit_recent`
  - `telegram_runtime_status`
  - `operational_logs_recent`
- la ruta `devops -> sudo -n /usr/local/sbin/davlos-openclaw-readonly <modo>` funciona
- el sudoers instalado coincide con el repo
- el drift menor repo ↔ host del helper no cambia superficie ni allowlist

## tabla de evidencias operativas

| área | estado observado en host | conclusión |
| --- | --- | --- |
| runtime state | `restricted_operator_state.json` en `root:root 0600` | el state store vive hoy en boundary root-only |
| lockfile | `.lock` en `root:root 0600` | el modelo actual del lock es compatible con writer root |
| writer identity | `openclaw-telegram-bot.service` ejecuta como `root:root` | existe writer root efectivo confirmado |
| aislamiento contenedor | `openclaw-gateway` corre como `node` y no monta `broker/state` | no hay evidencia de writer contenedor sobre ese state |
| helper instalado | helper root-owned, 5 modos, ejecución correcta | la observabilidad readonly cerrada existe realmente en host |
| sudoers instalado | `0440`, allowlist exacta de 5 modos | `devops` obtiene solo la superficie prevista |
| funcionalidad helper | `runtime_summary`, `broker_state_console`, `broker_audit_recent`, `telegram_runtime_status` y `operational_logs_recent` responden | el helper es operativo como vía real de inspección |
| exposición observable | `operational_logs_recent` muestra contexto acotado de units permitidas | hay utilidad operativa sin evidencia de secretos obvios en la muestra |

## riesgos residuales no bloqueantes

- `operational_logs_recent` expone metadata operativa lateral limitada de units permitidas; en la muestra no aparecieron secretos obvios
- el modelo del `.lock` es correcto para el estado root-only actual, pero debe reevaluarse si aparece un writer no root
- el helper instalado aún no incorpora la mejora menor del repo para hacer tail del audit log por streaming

## drift menor repo ↔ host aún existente

El drift menor confirmado es solo este:

- el helper instalado todavía usa lectura completa del audit log y luego recorte de últimas líneas
- el repo ya cambió ese punto a lectura por streaming con `deque`
- el repo añade comentarios aclaratorios sobre el alcance cerrado de `operational_logs_recent`

Juicio:

- el drift existe
- no cambia la superficie expuesta
- no cambia la allowlist
- no invalida el baseline prudente

## criterio de por qué esto ya no bloquea el baseline

El baseline ya no queda bloqueado porque:

- el supuesto crítico del repo sobre writer identity/permisos homogéneos sí queda respaldado por host
- helper y sudoers están instalados con ownership y modos restrictivos
- la ruta real de uso por `devops` funciona
- la superficie readonly es cerrada, útil y no equivale a abrir acceso general a `/opt/automation` ni a `journald`
- el drift restante entre repo y host es menor y no altera el contrato de seguridad observado

## qué queda pendiente

- sincronizar el helper instalado con la última revisión del repo en una intervención host-side controlada
- mantener vigilancia sobre la aparición de writers no root sobre `restricted_operator_state.json`
- seguir tratando como frentes separados cualquier endurecimiento posterior de firewall, inference-gateway, Telegram o UFW

## qué no debe tocarse sin nueva validación

- ownership o permisos de `/opt/automation/agents/openclaw/broker/state`
- modelo de writers del `restricted_operator_state.json`
- allowlist y alcance de `/usr/local/sbin/davlos-openclaw-readonly`
- `/etc/sudoers.d/davlos-openclaw-readonly`
- cualquier cambio que introduzca writers no root sobre el state file sin reevaluar el modelo del `.lock`

## siguiente paso recomendado

- sincronizar el helper instalado con la última revisión del repo en una intervención host-side controlada

## vigilancia futura

- no introducir writers no root sobre `restricted_operator_state.json` sin reevaluar explícitamente el modelo del `.lock`

## parche pendiente para obsi-claw-AI_agent

Actualizar el repo de producto con un reflejo documental breve y explícito de este baseline validado.

Cambio recomendado:

- añadir un documento nuevo de evidencia o estado, por ejemplo:
  - `docs/evidence/OPENCLAW_BASELINE_PRUDENTE_VALIDADO_2026-04-08.md`
- actualizar el documento agregador de estado operativo que ya use el repo de producto, por ejemplo:
  - `docs/ESTADO_GLOBAL.md`
  - o el equivalente vigente de semáforo/estado si es el que hoy concentra OpenClaw

Mensaje documental mínimo que debería quedar:

- el boundary OpenClaw ya no está solo “operativo”
- queda `validable como baseline prudente` por validación readonly host-side
- el runtime state del restricted operator y su `.lock` operan hoy en modelo root-only compatible
- el helper readonly y su sudoers están instalados con ownership restrictivo y superficie cerrada
- el drift repo ↔ host restante del helper es menor y no bloquea el baseline
- la fuente de verdad operativa sigue siendo `davlos-control-plane`, no el repo de producto

## conclusión operativa final

OpenClaw puede tratarse desde ahora como boundary con `baseline prudente validado` en host.

Eso no significa “hardening final cerrado”.
Sí significa que el núcleo operativo actual ya tiene una base observable, trazable y suficientemente coherente como para dejar de tratar este punto como bloqueo de baseline.
