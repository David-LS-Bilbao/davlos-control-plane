# OpenClaw Boundary Fix 2026-04-01

## objetivo

Ejecutar una Fase 0.6 correctiva para cerrar el boundary interno de `OpenClaw` sin introducir features nuevas y sin tocar `main`.

## alcance de esta intervención

- diagnosticar la causa del bind público de `inference-gateway`
- definir la corrección mínima segura
- intentar aplicarla solo si existe una vía root-safe y reversible
- revalidar el boundary y el flujo `OpenClaw -> inference-gateway`

Fuera de alcance:

- broker restringido
- policy store
- menú de capacidades
- Telegram/chat
- allowlist completa de egress
- cambios sobre `n8n`, `Verity`, `NPM`, `WireGuard` o `PostgreSQL`

## problema detectado

En la Fase 0.5 se confirmó que `inference-gateway`:

- respondía en `127.0.0.1:11440`
- respondía en `172.22.0.1:11440`
- y también respondía en la IP pública del host

Eso rompe la expectativa de boundary interno para el gateway de inferencia.

## evidencia recopilada

### servicio efectivo

`systemctl cat inference-gateway.service` mostró:

- `EnvironmentFile=/opt/automation/inference-gateway/host.env`
- `ExecStart=/usr/bin/python3 /opt/automation/inference-gateway/bin/ollama-proxy.py`

### listeners del host

`ss -lntp` mostró:

- `127.0.0.1:18789` en escucha
- `0.0.0.0:11440` en escucha
- `*:11434` para Ollama

### probes HTTP

Se validó respuesta correcta en:

- `http://127.0.0.1:11440/healthz`
- `http://127.0.0.1:11440/v1/models`
- `http://172.22.0.1:11440/healthz`
- `http://212.227.159.131:11440/healthz`

La respuesta por IP pública confirma exposición fuera de loopback.

### flujo OpenClaw

Se validó:

- `http://127.0.0.1:18789/` devuelve HTML válido de `OpenClaw Control`
- un handshake WS mínimo a `ws://127.0.0.1:18789` devuelve `connect.challenge`

Esto confirma que OpenClaw sigue operativo a nivel HTTP/WS.

## causa raíz

### causa raíz inmediata

El runtime efectivo de `inference-gateway` está arrancando con un bind amplio equivalente a `0.0.0.0:11440`.

La evidencia directa es:

- el listener real observado en `ss -lntp`
- la respuesta correcta desde la IP pública
- la existencia de un `host.env` root-owned que alimenta el proceso vía `systemd`

### causa raíz de diseño

El contrato actual intenta satisfacer dos caminos a la vez:

- validación host-side por `127.0.0.1:11440`
- consumo desde OpenClaw por `172.22.0.1:11440`

Con un único parámetro tipo `INFERENCE_BIND_HOST`, ese requisito empuja con facilidad a una solución insegura de bind ancho (`0.0.0.0`) para cubrir ambos caminos con un solo socket.

El template no versionado revisado en el repo apunta a esta tensión:

- `templates/inference-gateway/inference-gateway.env.example` define `INFERENCE_BIND_HOST=127.0.0.1`
- `templates/inference-gateway/ollama-proxy.py` resuelve un único `BIND_HOST`
- la documentación vigente sigue exigiendo accesibilidad tanto por loopback como por `172.22.0.1`

Conclusión:

- el problema no es solo de un valor mal puesto
- también hay un hueco en el contrato operativo: un único bind host no modela bien el boundary deseado

## corrección mínima segura recomendada

### objetivo de la corrección

Mantener:

- `127.0.0.1:11440` para validación host-side
- accesibilidad desde OpenClaw por el camino interno requerido

Y eliminar:

- respuesta por IP pública del host

### corrección técnica recomendada

No usar `0.0.0.0`.

La corrección mínima segura recomendada es:

1. ajustar el proxy para escuchar solo en dos direcciones explícitas:
   - `127.0.0.1`
   - `172.22.0.1`
2. reiniciar únicamente `inference-gateway.service`
3. revalidar:
   - `127.0.0.1:11440/healthz`
   - `127.0.0.1:11440/v1/models`
   - `172.22.0.1:11440/healthz`
   - no respuesta por IP pública
   - continuidad de OpenClaw por HTTP/WS

### por qué esta es la opción conservadora

- no toca OpenClaw
- no toca Docker ni redes existentes
- no abre nuevas superficies
- no obliga aún a meter firewall adicional ni nuevas capas
- es reversible con rollback simple del script/env y reinicio del servicio

## intento de aplicación en esta sesión

Se intentó acceder a:

- `/opt/automation/inference-gateway/host.env`
- `/opt/automation/inference-gateway/bin/ollama-proxy.py`
- inspección Docker readonly de `openclaw-gateway`

Resultado:

- `Permission denied` en runtime root-owned
- `sudo -n` requiere password
- `docker.sock` no accesible desde la sesión actual

`sudo -n -l` confirma:

- el usuario `devops` puede ejecutar `sudo`, pero no dispone de una vía `NOPASSWD` útil para `inference-gateway`
- la única excepción `NOPASSWD` visible es el helper readonly de `n8n`

## estado del cambio aplicado

No se aplicó cambio runtime en esta sesión.

Motivo:

- no existe desde esta sesión una vía segura, acotada y sin password para editar el runtime de `inference-gateway`
- no es aceptable improvisar cambios inseguros ni forzar un workaround no auditado

## validaciones ejecutadas

### realizadas

- `systemctl cat inference-gateway.service`
- `systemctl show -p FragmentPath -p EnvironmentFiles -p ExecStart inference-gateway.service`
- `systemctl status inference-gateway.service --no-pager`
- `ss -lntp`
- `curl http://127.0.0.1:11440/healthz`
- `curl http://127.0.0.1:11440/v1/models`
- `curl http://172.22.0.1:11440/healthz`
- `curl http://212.227.159.131:11440/healthz`
- `curl http://127.0.0.1:18789/`
- comprobación WS mínima a `ws://127.0.0.1:18789`

### no completadas por permisos

- lectura del `host.env` efectivo
- lectura del proxy Python efectivo del runtime
- cambio de configuración del runtime
- reinicio controlado de `inference-gateway.service`
- confirmación Docker readonly de:
  - `openclaw-gateway status`
  - `openclaw-gateway health`
  - `agents_net`
  - bind efectivo por inspección Docker

## estado final del boundary

### logrado

- el problema está identificado y acotado con evidencia suficiente
- OpenClaw sigue operativo
- no se han expuesto secretos durante la validación

### no logrado todavía

- `inference-gateway` sigue respondiendo por IP pública
- el boundary interno no puede considerarse cerrado en esta sesión

## estado de validación Docker readonly

Sigue bloqueada por permisos.

Evidencia:

- `docker inspect ...` falla por acceso a `/var/run/docker.sock`
- `sudo -n docker inspect ...` falla porque `sudo` requiere password

Estado a consignar:

- `openclaw-gateway running/healthy`: `NO_RECONFIRMADO_POR_PERMISOS`
- `agents_net` presente/aislada: `NO_RECONFIRMADO_POR_PERMISOS`

## backlog abierto

### P0

- ejecutar una ventana corta con privilegio root efectivo para:
  - inspeccionar `host.env`
  - inspeccionar el proxy real
  - aplicar el fix de bind
  - reiniciar solo `inference-gateway.service`
  - revalidar no respuesta por IP pública

### P0

- cerrar la validación Docker readonly de `openclaw-gateway` y `agents_net` desde una sesión con acceso suficiente

### P1

- decidir si el contrato definitivo del gateway será:
  - dual bind explícito (`127.0.0.1` + `172.22.0.1`)
  - o un camino interno alternativo equivalente que no requiera bind público

## recomendación

No pasar a Fase 1 mientras persistan dos bloqueos:

- `inference-gateway` expuesto por IP pública
- validación Docker readonly incompleta de `openclaw-gateway` y `agents_net`

La siguiente intervención debe ser operativa y corta, con root efectivo y alcance estrictamente acotado a `inference-gateway.service`.
