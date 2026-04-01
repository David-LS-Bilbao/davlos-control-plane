# OpenClaw Baseline Runtime Validation 2026-04-01

## objetivo

Cerrar una Fase 0.5 de validación operativa corta sobre el runtime real del VPS después del baseline documental de `2026-04-01`, sin introducir nuevas features ni tocar `main`.

## rama y baseline de referencia

- rama validada: `codex/openclaw-console-readonly`
- baseline de referencia: `docs/reports/OPENCLAW_BASELINE_AUDIT_2026-04-01.md`
- commit baseline previo: `c7d8354`

## alcance de esta validación

Validaciones readonly, mínimas y justificadas sobre:

- `OpenClaw`
- `inference-gateway`
- consola readonly
- flujo general `OpenClaw -> inference-gateway`

Fuera de alcance:

- reinicios
- cambios de runtime
- apertura/cierre de red
- hardening adicional
- nuevas capacidades del producto

## comprobaciones ejecutadas

### estado git y baseline

- rama activa confirmada: `codex/openclaw-console-readonly`
- baseline documental revisado: `docs/reports/OPENCLAW_BASELINE_AUDIT_2026-04-01.md`
- worktree no limpio por tres no versionados preexistentes, sin relación directa con esta validación

### consola readonly

Se ejecutó:

- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-health`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-logs`

Resultado:

- la consola sigue siendo usable en modo degradado cuando no hay acceso directo a Docker
- no imprimió `.env`
- no imprimió tokens, `apiKey` ni cabeceras de autorización en las comprobaciones realizadas
- sigue mostrando información útil del host para `inference-gateway`

### inference-gateway

Se validó:

- `systemctl status inference-gateway.service --no-pager`
- `curl http://127.0.0.1:11440/healthz`
- `curl http://127.0.0.1:11440/v1/models`
- `curl http://172.22.0.1:11440/healthz`

Resultado:

- `inference-gateway.service` estaba `active (running)`
- `/healthz` respondió `status=ok`
- `/v1/models` respondió con el modelo permitido `qwen2.5:3b`
- el endpoint previsto para OpenClaw por `172.22.0.1:11440` respondió correctamente

### OpenClaw

Se validó:

- `curl http://127.0.0.1:18789/`
- comprobación WebSocket mínima contra `ws://127.0.0.1:18789`

Resultado:

- el bind local `127.0.0.1:18789` sigue respondiendo
- la UI devuelve HTML válido de `OpenClaw Control`
- el endpoint WebSocket abre y devuelve `connect.challenge` con `nonce` efímero
- no se expusieron secretos en las respuestas observadas

### listeners del host

Se validó:

- `ss -lntp`

Resultado:

- `127.0.0.1:18789` sigue en escucha
- `11440` aparece en escucha host-side
- `11434` sigue expuesto para Ollama

## puntos confirmados

- el baseline sigue siendo coherente para el bind local de OpenClaw
- el endpoint efectivo `OpenClaw -> http://172.22.0.1:11440/v1` sigue teniendo soporte real en host
- la consola readonly sigue útil y no mostró contenido sensible en esta validación
- el flujo mínimo de disponibilidad HTTP/WS de OpenClaw está vivo
- `inference-gateway` sigue operativo y responde por los paths esperados

## puntos no reconfirmados completamente

- no fue posible reconfirmar desde esta sesión el estado Docker exacto `running/healthy` de `openclaw-gateway`
- no fue posible reconfirmar por inspección Docker la presencia e aislamiento de `agents_net`

Motivo:

- no hay acceso efectivo al socket Docker desde la sesión actual
- `sudo -n docker inspect ...` devuelve `sudo: a password is required`
- la propia consola readonly degrada correctamente y declara la falta de acceso directo a Docker

Interpretación conservadora:

- el runtime de OpenClaw está operativo a nivel de HTTP/WS
- la salud Docker exacta y el detalle de `agents_net` quedan `NO_RECONFIRMADOS_POR_PERMISOS` en esta Fase 0.5

## desalineaciones detectadas contra el baseline

### alta

- `inference-gateway` no solo responde en `127.0.0.1:11440` y `172.22.0.1:11440`; también responde en la IP pública del host
- `ss -lntp` muestra escucha en `0.0.0.0:11440`
- un `curl` contra la IP pública del propio host en `:11440/healthz` respondió correctamente

## evaluación del riesgo

### crítico

- el bind efectivo actual de `inference-gateway` amplía la superficie más allá de lo esperado para un boundary interno
- esto contradice la intención de no exposición pública del gateway y debe tratarse como bloqueo operativo antes de Fase 1

### altos

- la imposibilidad de inspección Docker desde esta sesión limita el cierre total del baseline sobre `running/healthy` y `agents_net`
- `templates/inference-gateway/` existe no versionado y mezcla material potencialmente útil con una opción contenedorizada que no es la decisión operativa actual

### medios

- la consola readonly queda útil, pero hoy depende de degradación por permisos y no puede cerrar por sí sola todas las comprobaciones de Docker

## clasificación de no versionados preexistentes

### dejar fuera por ahora

- `scripts/prechecks/n8n/45_n8n_workflow_inventory_readonly.sh`
  - parece un helper válido de `n8n`, pero queda fuera del alcance OpenClaw y su publicación debe ir en un tramo separado de trazabilidad `n8n`
- `templates/inference-gateway/docker-compose.yaml`
  - describe una variante contenedorizada que no coincide con la decisión operativa actual host-side por `systemd`
- `templates/inference-gateway/inference-gateway.env.example`
  - útil como referencia, pero debe revisarse junto con la decisión final de bind y despliegue antes de incluirse
- `templates/inference-gateway/ollama-proxy.py`
  - parece material valioso para trazabilidad, pero debe revisarse y separarse de la variante contenedorizada antes de versionarse

### ignorar

- `templates/inference-gateway/__pycache__/ollama-proxy.cpython-312.pyc`
  - artefacto generado, no debe versionarse

### no incluir en el repo como evidencia útil

- `evidence/prechecks/n8n/2026-03-31/45_n8n_workflow_inventory_readonly.txt`
  - solo contiene errores por falta de acceso Docker y no añade valor estable como evidencia final

## decisión recomendada

No avanzar a Fase 1 de consolidación de la zona de agentes hasta cerrar o aceptar explícitamente el riesgo de exposición de `inference-gateway` en interfaz no loopback.

## siguiente paso recomendado

Ejecutar una intervención mínima y específica, separada de esta validación, para:

- corregir el bind efectivo de `inference-gateway` si se confirma que no debe exponerse fuera de loopback/bridge controlado
- revalidar después `running/healthy` y `agents_net` desde una sesión con acceso readonly real a Docker
- decidir el destino de `templates/inference-gateway/` en un cambio documental separado

## cambios aplicados en esta intervención

- se añade este addendum documental
- no se modificó runtime
- no se reinició ningún servicio
- no se tocaron `Verity`, `NPM`, `WireGuard` ni `PostgreSQL`
