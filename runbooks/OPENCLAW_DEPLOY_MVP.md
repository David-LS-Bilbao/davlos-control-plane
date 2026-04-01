# Runbook MVP: despliegue de OpenClaw en zona separada

## objetivo

Levantar OpenClaw en una zona propia sin tocar `n8n`, NPM ni WireGuard.

## topología real del MVP

- OpenClaw corre en Docker con el servicio `openclaw-gateway`.
- La red usada es `agents_net`, declarada como red Docker externa.
- El bind host es `127.0.0.1:18789`.
- La inferencia sale por `http://172.22.0.1:11440/v1`.
- El backend real de inferencia es Ollama en host vía `127.0.0.1:11434`, mediado por `inference-gateway`.

## layout objetivo

- `/opt/automation/agents/openclaw/compose`
- `/opt/automation/agents/openclaw/config`
- `/opt/automation/agents/openclaw/state`
- `/opt/automation/agents/openclaw/logs`
- `/etc/davlos/secrets/openclaw`

## imagen fijada para el primer arranque

- `ghcr.io/openclaw/openclaw:2026.2.3`

## configuración mínima efectiva

- `COMPOSE_PROJECT_NAME=openclaw`
- `OPENCLAW_GATEWAY_PORT=18789`
- `OPENCLAW_GATEWAY_TOKEN` generado en el runtime `.env`
- proveedor local `davlos-local`
- modelo primario `davlos-local/qwen2.5:3b`

## despliegue

1. Confirmar que `inference-gateway` en host responde en:
   - `http://127.0.0.1:11440/healthz`
   - `http://172.22.0.1:11440/v1/models`
2. Ejecutar el despliegue controlado:
   - `sudo bash /opt/control-plane/scripts/agents/openclaw/30_first_local_deploy.sh`
3. Ese script:
   - asegura layout y permisos del runtime
   - materializa `openclaw.json`
   - fija `COMPOSE_PROJECT_NAME=openclaw`
   - crea o valida `agents_net` en `172.22.0.0/16`
   - recrea `openclaw-gateway`
4. Validar:
   - `sudo docker ps --filter name=openclaw-gateway`
   - `sudo docker inspect openclaw-gateway --format 'image={{.Config.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}'`
   - `sudo docker inspect openclaw-gateway --format '{{json .NetworkSettings.Networks}}'`
   - `sudo docker inspect openclaw-gateway --format '{{json .Mounts}}'`
   - `sudo docker inspect openclaw-gateway --format '{{json .HostConfig.SecurityOpt}}'`
   - `sudo docker inspect openclaw-gateway --format '{{json .HostConfig.CapDrop}}'`
   - confirmación de que está en `agents_net`
   - confirmación de que no usa `verity_network`
   - comprobación TCP MVP sobre `127.0.0.1:18789`

Nota de seguridad:

- no imprimir el `.env` real del runtime
- evitar `docker inspect` bruto cuando no sea imprescindible, porque puede exponer variables de entorno sensibles del contenedor
- revisar logs con criterio y sin copiar tokens, payloads o cabeceras de autenticación a evidencias persistentes

## criterio de aceptación

- OpenClaw solo visible por loopback/VPN
- red separada
- bind host solo por loopback
- OpenClaw usando `http://172.22.0.1:11440/v1`
- sin secretos cloud necesarios para este primer MVP local
- rollback simple

## observabilidad readonly desde consola

Una vez desplegado, la consola MVP puede usarse en modo solo lectura para mostrar el estado combinado de `OpenClaw` e `inference-gateway` sin tocar el runtime.

Comandos útiles:

- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-health`
- `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-logs`

La salida esperada incluye, cuando la sesión tiene acceso suficiente:

- estado y health del contenedor `openclaw-gateway`
- bind local `127.0.0.1:18789`
- red `agents_net` e IP del contenedor
- mounts relevantes
- `security_opt` y `cap_drop`
- endpoint de inferencia configurado para OpenClaw
- estado de `inference-gateway.service`
- respuesta local de `http://127.0.0.1:11440/healthz`

Si Docker o journal no están disponibles en la sesión actual, la consola degrada con mensaje claro y no rompe otros menús.
