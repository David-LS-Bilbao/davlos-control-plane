# Seguridad MVP de la zona de agentes

## objetivo

Separar OpenClaw y futuros agentes del resto del VPS con una postura segura por defecto y rollback simple.

## baseline de seguridad

- red dedicada `agents_net`
- bind del gateway solo a `127.0.0.1:18789`
- sin reutilizar `verity_network`
- secretos fuera del workspace del agente
- sin acceso implícito a `/root`, `n8n`, NPM o WireGuard

## layout previsto

- runtime: `/opt/automation/agents/openclaw`
- secretos: `/etc/davlos/secrets/openclaw`
- plantillas y runbooks: `control-plane`

## controles mínimos

- `no-new-privileges`
- `cap_drop: ALL`
- límites de CPU/memoria/PIDs
- logs y estado visibles, acciones de escritura controladas aparte

## supuestos y límites

- OpenClaw debe quedar como trust boundary separada de la operación general
- el gateway no debe exponerse públicamente
- acceso remoto solo por VPN, túnel o proxy controlado
- la implantación real depende de revisar imagen/config final y secretos
