# Agentes DAVLOS

## alcance

Este documento fija el contrato operativo actual de la zona de agentes en DAVLOS.

No define un roadmap completo de producto.
No autoriza cambios de runtime por sí solo.
No sustituye la evidencia operativa validada en runtime.

## estado consolidado actual

- existe un único runtime de agente documentado y validado: `OpenClaw`
- el servicio desplegado es `openclaw-gateway`
- el runtime host-side vive bajo `/opt/automation/agents/openclaw`
- la ruta host-side de secretos reservada es `/etc/davlos/secrets/openclaw`
- la red usada es `agents_net`
- el bind host publicado para el gateway es `127.0.0.1:18789`
- OpenClaw consume inferencia por `http://172.22.0.1:11440/v1`
- el upstream real de inferencia es `inference-gateway.service` en host
- `inference-gateway` escucha solo en `127.0.0.1:11440` y `172.22.0.1:11440`
- `inference-gateway` ya no responde por la IP pública del host
- la reachability `agents_net -> 172.22.0.1:11440` quedó validada en runtime
- la consola `DAVLOS VPN Console` expone observabilidad readonly para `OpenClaw` e `inference-gateway`

## trust boundary operativa

La zona de agentes actual se compone de dos piezas separadas:

- `openclaw-gateway`
  - proceso de agente en contenedor
  - visible al host solo por `127.0.0.1:18789`
  - conectado a `agents_net`
- `inference-gateway.service`
  - boundary host-side delante de Ollama
  - upstream fijo a `127.0.0.1:11434`
  - único backend de inferencia permitido hoy para OpenClaw

Motivo de la separación:

- OpenClaw no habla con Ollama directo
- el boundary de inferencia reduce acoplamiento con la API nativa de Ollama
- el gateway deja una superficie northbound mínima y controlable
- la política de bind y reachability puede endurecerse sin tocar el contenedor del agente

## contrato operativo actual

### OpenClaw

- contenedor: `openclaw-gateway`
- red: `agents_net`
- bind permitido: `127.0.0.1:18789 -> 18789/tcp`
- mounts esperados:
  - `/workspace/config` readonly
  - `/workspace/state` read-write
  - `/workspace/logs` read-write
  - `/run/secrets/openclaw` readonly
- hardening base del contenedor:
  - `no-new-privileges`
  - `cap_drop: ALL`
  - sin publicación en IP pública

### inference-gateway

- runtime: `/opt/automation/inference-gateway`
- gestión: `systemd`
- bind permitido:
  - `127.0.0.1:11440`
  - `172.22.0.1:11440`
- bind no permitido:
  - IP pública del host
- contrato northbound mínimo:
  - `GET /healthz`
  - `GET /v1/models`
  - `POST /v1/chat/completions`

### secretos host-side

- el repositorio no contiene secretos reales
- `OPENCLAW_GATEWAY_TOKEN` sigue siendo el único secreto operativo mínimo del MVP local
- hoy puede vivir en el `.env` root-owned del runtime de OpenClaw
- `/etc/davlos/secrets/openclaw` queda reservado para crecimiento posterior sin reestructurar mounts ni contrato host-side

## límites explícitos de acceso

### qué puede tocar OpenClaw hoy

- su propio bind local en `127.0.0.1:18789`
- su runtime bajo `/opt/automation/agents/openclaw`
- el boundary de inferencia aprobado en `172.22.0.1:11440`

### qué no debe tocar

- `n8n`
- NPM
- WireGuard
- PostgreSQL
- `verity_network`
- Ollama directo como contrato de aplicación
- Internet libre
- secretos reales en el workspace o en el repo

## dependencias explícitas actuales

- Docker para `openclaw-gateway`
- red Docker `agents_net`
- `inference-gateway.service`
- Ollama local en `127.0.0.1:11434`
- regla host-side efectiva que permite `agents_net -> 172.22.0.1:11440`

## postura operativa actual

- trust boundary separada respecto a `n8n`, NPM, WireGuard y PostgreSQL
- mínimo privilegio en el contenedor
- sin credenciales cloud necesarias en este MVP local
- cambios operativos posteriores deben ser pequeños, reversibles y con evidencia
- el siguiente tramo de evolución es broker restringido, no nuevas capacidades prematuras

## riesgos residuales conocidos

- la allowlist real de egress para `agents_net` sigue pendiente
- la imagen sigue fijada por tag revisado y no por digest operativo final
- el `healthcheck` actual de OpenClaw es suficiente para MVP, pero no equivale a política final de liveness/readiness
- existe drift operativo en UFW entre configuración declarada y reglas runtime cargadas; hoy no bloquea la operación, pero debe normalizarse antes de endurecimientos posteriores

## superficie disponible hoy

- despliegue y rollback documentados en runbooks
- observabilidad readonly desde consola:
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-health`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-logs`

## lo que no debe darse por implementado

- broker restringido
- policy store
- menú final de control de capacidades con escritura
- integración Telegram
- chat operativo final
- acciones A/B/C/D
- allowlist final de egress aplicada
- política final de secretos para proveedores externos

## documentos de referencia

- `docs/INFERENCE_GATEWAY_OLLAMA_MVP.md`
- `docs/AGENT_ZONE_SECURITY_MVP.md`
- `docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md`
- `docs/OPENCLAW_SECURITY_BOOTSTRAP_MVP.md`
- `docs/OPENCLAW_HOST_SECRETS_CONTRACT_MVP.md`
- `runbooks/OPENCLAW_DEPLOY_MVP.md`
- `runbooks/OPENCLAW_ROLLBACK_MVP.md`
- `docs/reports/OPENCLAW_BOUNDARY_RUNTIME_FIX_2026-04-01.md`
- `docs/reports/OPENCLAW_AGENTS_NET_REACHABILITY_FIX_2026-04-01.md`
