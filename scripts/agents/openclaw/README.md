# OpenClaw runtime staging scripts

## propósito

Estos scripts preparan y validan el scaffold mínimo del runtime de OpenClaw sin desplegar contenedores ni tocar servicios existentes.

## qué preparan

- layout base bajo `/opt/automation/agents/openclaw`
- ruta vacía de secretos en `/etc/davlos/secrets/openclaw`
- copia de:
  - `templates/openclaw/docker-compose.yaml`
  - `templates/openclaw/openclaw.env.example`
  - `templates/openclaw/openclaw.json.example`

## qué NO hacen

- no crean `agents_net`
- no arrancan contenedores
- no llaman a Docker
- no crean secretos reales
- no inventan `config/openclaw.json` como configuración runtime real

## decisión sobre `config/openclaw.json`

Se elige la opción A: no crear `config/openclaw.json` en este tramo y dejarlo marcado como pendiente explícito, porque todavía no hay contrato confirmado de configuración real para OpenClaw.

- `config/openclaw.json.example`
  - contrato bootstrap copiado al runtime staged
  - sirve como referencia no operativa
- `config/openclaw.json`
  - configuración runtime real
  - sigue pendiente de validar antes del deploy

## scripts

### `10_stage_runtime.sh`

- crea el layout base si no existe
- crea la ruta de secretos si no existe
- copia el compose y el `.env` solo si faltan
- no sobrescribe archivos existentes

### `20_validate_runtime_readiness.sh`

- comprueba layout, archivos y claves mínimas del `.env`
- detecta si `OPENCLAW_IMAGE` sigue siendo placeholder
- distingue entre `config/openclaw.json.example` y `config/openclaw.json`
- no depende de Docker

## cómo ejecutarlos

```bash
sudo bash /opt/control-plane/scripts/agents/openclaw/10_stage_runtime.sh
sudo bash /opt/control-plane/scripts/agents/openclaw/20_validate_runtime_readiness.sh
```

## estados del validador

- `NOT_STAGED`
  - no existe todavía el scaffold básico
- `STAGED_INCOMPLETE`
  - faltan rutas, archivos o claves mínimas, incluida la ruta de secretos si no existe
- `STAGED_READY_FOR_IMAGE_AND_SECRETS`
  - el staging base está hecho y la ruta de secretos ya existe, pero faltan imagen real preferiblemente fijada por digest, contenido de secretos y/o `config/openclaw.json`
  - si existe `config/openclaw.json.example`, se reporta como contrato bootstrap presente
- `STAGED_READY_FOR_DEPLOY_PRECHECKS`
  - el runtime ya tiene scaffold, imagen no-placeholder, ruta de secretos con contenido y `config/openclaw.json`; el siguiente tramo ya puede ser precheck antes del deploy real
