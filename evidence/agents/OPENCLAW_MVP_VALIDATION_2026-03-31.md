# OpenClaw MVP Validation 2026-03-31

## estado

- despliegue real ejecutado en host
- contenedor `openclaw-gateway` arrancado
- inferencia conectada al `inference-gateway` en host
- bootstrap de seguridad cerrado para MVP local
- sin impacto en `n8n`, NPM, WireGuard ni PostgreSQL

## validación actual

- runtime real materializado en host:
  - `/opt/automation/agents/openclaw/compose`
  - `/opt/automation/agents/openclaw/config`
  - `/opt/automation/agents/openclaw/state`
  - `/opt/automation/agents/openclaw/logs`
  - `/etc/davlos/secrets/openclaw`
- imagen desplegada:
  - `ghcr.io/openclaw/openclaw:2026.2.3`
- proyecto Compose aislado:
  - `COMPOSE_PROJECT_NAME=openclaw`
- endpoint de inferencia usado por OpenClaw:
  - `http://172.22.0.1:11440/v1`
- modelo efectivo:
  - `davlos-local/qwen2.5:3b`
- red:
  - `agents_net`
- health/runtime observados en el primer arranque estable:
  - `status=running`
  - `restart_count=0`
  - `health=healthy`
  - escucha en `ws://0.0.0.0:18789`
  - comprobación TCP MVP correcta en `127.0.0.1:18789`
- el directorio `/etc/davlos/secrets/openclaw` puede permanecer vacío en este MVP local

## deuda técnica explícita

- decidir si se mantiene `2026.2.3`, `latest` o un pin por digest
- endurecer healthcheck si deja de bastar la comprobación TCP MVP
- definir política final de secretos si se introduce proveedor externo
- validar funcionalmente el uso real de OpenClaw sobre el gateway ya desplegado

## observabilidad readonly integrada

- `DAVLOS VPN Console` ya expone una vista readonly para `OpenClaw` e `inference-gateway`
- comandos operativos mínimos:
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-health`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-logs`
- el panel muestra:
  - estado y health del runtime de OpenClaw cuando Docker está disponible en la sesión
  - bind local, red, container IP, mounts y `security_opt`/`cap_drop`
  - endpoint de inferencia configurado para OpenClaw
  - estado y `healthz` de `inference-gateway`
  - últimos logs útiles de ambos cuando la sesión puede leerlos
- si la sesión no tiene acceso suficiente a Docker o journal, la consola degrada con mensaje claro y mantiene visible el resumen host-side de `inference-gateway`

## siguiente hito técnico

Ejecutar pruebas funcionales sobre el despliegue ya operativo sin reabrir la base de red ni rediseñar la topología.
