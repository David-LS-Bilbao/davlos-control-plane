# Runbook MVP: despliegue de OpenClaw en zona separada

## objetivo

Levantar OpenClaw en una zona propia sin tocar `n8n`, NPM ni WireGuard.

## layout objetivo

- `/opt/automation/agents/openclaw/compose`
- `/opt/automation/agents/openclaw/config`
- `/opt/automation/agents/openclaw/state`
- `/opt/automation/agents/openclaw/logs`
- `/etc/davlos/secrets/openclaw`

## pasos

1. Crear layout objetivo bajo `/opt/automation/agents/openclaw`.
2. Copiar `templates/openclaw/docker-compose.yaml` y `templates/openclaw/openclaw.env.example`.
3. Elegir imagen revisada o build local válido de OpenClaw.
4. Preparar config y token fuera del workspace del agente en `/etc/davlos/secrets/openclaw`.
5. Crear red `agents_net`.
6. Levantar `openclaw-gateway` con bind `127.0.0.1:18789`.
7. Validar:
   - `docker ps`
   - `docker logs`
   - health del contenedor
   - confirmación de que no usa `verity_network`
   - confirmación de que el gateway no está expuesto en público

## criterio de aceptación

- OpenClaw solo visible por loopback/VPN
- secretos fuera del agente
- red separada
- rollback simple
