# OpenClaw Boundary Runtime Fix 2026-04-01

## objetivo

Ejecutar una corrección operativa mínima y auditada sobre `inference-gateway`, revalidar el boundary host-side y cerrar la validación Docker readonly real de `openclaw-gateway` y `agents_net`.

## alcance ejecutado

- inspección root efectiva de:
  - `/etc/systemd/system/inference-gateway.service`
  - `/opt/automation/inference-gateway/host.env`
  - `/opt/automation/inference-gateway/bin/ollama-proxy.py`
- corrección runtime mínima sobre `inference-gateway`
- reinicio exclusivo de `inference-gateway.service`
- revalidación host-side y Docker readonly
- comprobación explícita de reachability desde `openclaw-gateway`

## evidencia raíz confirmada

### servicio efectivo

`systemctl cat inference-gateway.service`:

- `EnvironmentFile=/opt/automation/inference-gateway/host.env`
- `ExecStart=/usr/bin/python3 /opt/automation/inference-gateway/bin/ollama-proxy.py`
- servicio ejecutado como `root`

### configuración efectiva antes del cambio

`/opt/automation/inference-gateway/host.env`:

- `INFERENCE_BIND_HOST=0.0.0.0`
- `INFERENCE_BIND_PORT=11440`

`/opt/automation/inference-gateway/bin/ollama-proxy.py`:

- el runtime resolvía un único `BIND_HOST`
- `ThreadingHTTPServer((BIND_HOST, BIND_PORT), OllamaProxyHandler)` usaba ese valor sin filtrado adicional

### evidencia de exposición pública antes del cambio

Antes del fix:

- `ss -lntp` mostró `0.0.0.0:11440`
- `curl http://212.227.159.131:11440/healthz` respondió `200`

Conclusión:

- la causa raíz inmediata del bind público era directa y exacta:
  - `host.env` fijaba `0.0.0.0`
  - el proxy hacía bind literal sobre ese valor

## corrección aplicada

### cambio runtime

Se aplicó un cambio mínimo al runtime root-owned:

1. se respaldaron:
   - `/opt/automation/inference-gateway/bin/ollama-proxy.py.bak-2026-04-01`
   - `/opt/automation/inference-gateway/host.env.bak-2026-04-01`
2. el proxy pasó de bind único a bind explícito múltiple
3. `host.env` quedó en:
   - `INFERENCE_BIND_HOST=127.0.0.1,172.22.0.1`
4. se reinició solo:
   - `inference-gateway.service`

### estado runtime final

`ss -lntp` tras el cambio:

- `127.0.0.1:11440` en escucha
- `172.22.0.1:11440` en escucha
- ya no aparece `0.0.0.0:11440`

## validación funcional final

### inference-gateway host-side

Correcto:

- `curl http://127.0.0.1:11440/healthz`
- `curl http://127.0.0.1:11440/v1/models`
- `curl http://172.22.0.1:11440/healthz`

Respuestas observadas:

- `/healthz` devuelve `status=ok`
- `/v1/models` devuelve el modelo permitido `qwen2.5:3b`

### no respuesta por IP pública

Correcto:

- `curl http://212.227.159.131:11440/healthz` falla con `curl: (7) Failed to connect`

Conclusión:

- el boundary público de `inference-gateway` quedó cerrado

### OpenClaw host-side

Correcto:

- `curl http://127.0.0.1:18789/` devuelve HTML válido de `OpenClaw Control`
- handshake WS mínimo manual a `ws://127.0.0.1:18789/` devuelve:
  - `HTTP/1.1 101 Switching Protocols`

## validación Docker readonly real

### openclaw-gateway

`docker inspect` filtrado confirmó:

- `state=running`
- `health=healthy`
- `restart=unless-stopped`
- `netmode=agents_net`
- bind publicado:
  - `18789/tcp => 127.0.0.1:18789`
- mounts relevantes:
  - `/workspace/config <= /opt/automation/agents/openclaw/config rw=false`
  - `/workspace/state <= /opt/automation/agents/openclaw/state rw=true`
  - `/workspace/logs <= /opt/automation/agents/openclaw/logs rw=true`
  - `/run/secrets/openclaw <= /etc/davlos/secrets/openclaw rw=false`
- red efectiva:
  - `agents_net`
  - `ip=172.22.0.2`
  - `gw=172.22.0.1`

### agents_net

`docker inspect` filtrado confirmó:

- `driver=bridge`
- `subnet=172.22.0.0/16`
- `gateway=172.22.0.1`
- `internal=false`
- `attachable=false`
- `scope=local`

## hallazgo crítico residual

### OpenClaw no alcanza inference-gateway por la ruta configurada

El runtime efectivo de OpenClaw sigue configurado con:

- `baseUrl=http://172.22.0.1:11440/v1`

Sin embargo, la validación desde el propio runtime Node del contenedor falló de forma repetible:

- `fetch('http://172.22.0.1:11440/healthz')`
- resultado:
  - `ConnectTimeoutError`
  - `attempted address: 172.22.0.1:11440`

Importante:

- el fallo persiste tanto con el bind seguro final (`127.0.0.1,172.22.0.1`) como con una comprobación temporal controlada en `0.0.0.0`
- por tanto, el timeout de `openclaw-gateway -> 172.22.0.1:11440` no queda explicado por el fix de bind del proxy
- el problema de reachability desde `agents_net` parece independiente y preexistente respecto al cierre del boundary público

## firewall / UFW

Durante la validación se observó una inconsistencia operativa:

- `ufw status` enumera reglas para `11440/tcp` en `br-0759beecc34d`
- la materialización observable de esas reglas no fue consistente durante la sesión
- se añadió una regla duplicada solo para comprobar materialización y se retiró al final

No se dejó un cambio final de firewall como parte del fix operativo.

## estado final del boundary

### logrado

- causa raíz del bind público confirmada con evidencia exacta
- `inference-gateway` ya no responde por la IP pública del host
- `inference-gateway` sigue operativo en:
  - `127.0.0.1:11440`
  - `172.22.0.1:11440`
- `openclaw-gateway` y `agents_net` quedan reconfirmados con Docker readonly real
- OpenClaw sigue sano por HTTP/WS host-side

### no resuelto en esta intervención

- reachability efectiva desde `openclaw-gateway` hacia `http://172.22.0.1:11440/v1`

## decisión sobre siguiente fase

### decisión

`NO-GO` para declarar la rama lista para Fase 1 en sentido estricto.

### motivo

Aunque el boundary público del `inference-gateway` quedó corregido, no existe evidencia satisfactoria de que OpenClaw pueda consumir inferencia por la ruta configurada en `agents_net`.

### siguiente paso recomendado

Abrir una intervención separada y acotada solo para `agents_net -> host bridge`, con foco en:

- trazado de reachability real hacia `172.22.0.1:11440`
- materialización efectiva de reglas host-side
- o revisión del contrato de acceso host desde OpenClaw si `172.22.0.1` no es el camino operativo real en este host

## artefactos tocados

Fuera del repo:

- `/opt/automation/inference-gateway/bin/ollama-proxy.py`
- `/opt/automation/inference-gateway/host.env`

En el repo:

- `docs/reports/OPENCLAW_BOUNDARY_RUNTIME_FIX_2026-04-01.md`
