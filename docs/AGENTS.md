# Agentes DAVLOS

## alcance

Este documento fija el baseline actual de la zona de agentes en DAVLOS.

No define un roadmap completo de producto.
No autoriza cambios de runtime por sí solo.
No sustituye la evidencia operativa del despliegue ya validado.

## estado actual confirmado

- existe un único runtime de agente documentado y validado: `OpenClaw`
- el servicio desplegado es `openclaw-gateway`
- el runtime vive bajo `/opt/automation/agents/openclaw`
- la ruta host-side de secretos es `/etc/davlos/secrets/openclaw`
- la red usada es `agents_net`
- el bind host publicado para el gateway es `127.0.0.1:18789`
- OpenClaw consume inferencia por `http://172.22.0.1:11440/v1`
- el upstream real de inferencia es `inference-gateway.service` en host
- la consola `DAVLOS VPN Console` ya expone observabilidad readonly para `OpenClaw` e `inference-gateway`

## postura operativa actual

- trust boundary separada respecto a `n8n`, NPM, WireGuard y PostgreSQL
- mínimo privilegio en el contenedor: `no-new-privileges` y `cap_drop: ALL`
- sin secretos reales en el repositorio
- sin credenciales cloud necesarias en este MVP local
- cambios operativos posteriores deben ser pequeños, reversibles y con evidencia

## superficie disponible hoy

- despliegue y rollback documentados en runbooks
- observabilidad readonly desde consola:
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-health`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-logs`

## lo que no debe darse por implementado

- broker restringido
- menú final de control de capacidades con escritura
- integración Telegram
- chat operativo final
- acciones A/B/C/D
- allowlist real de egress aplicada
- política final de secretos para proveedores externos

## documentos de referencia

- `docs/INFERENCE_GATEWAY_OLLAMA_MVP.md`
- `docs/AGENT_ZONE_SECURITY_MVP.md`
- `docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md`
- `docs/OPENCLAW_SECURITY_BOOTSTRAP_MVP.md`
- `docs/OPENCLAW_HOST_SECRETS_CONTRACT_MVP.md`
- `runbooks/OPENCLAW_DEPLOY_MVP.md`
- `runbooks/OPENCLAW_ROLLBACK_MVP.md`
- `evidence/agents/OPENCLAW_MVP_VALIDATION_2026-03-31.md`
