# OpenClaw MVP Validation 2026-03-31

## estado

- scaffold de runtime: preparado y ejecutado en host
- scripts de staging/validación: preparados
- artefactos de despliegue: preparados en `templates/openclaw`
- bootstrap de seguridad: documentado
- despliegue real en host: pendiente

## validación actual

- no existe `openclaw` instalado en host
- existe runtime staged en host:
  - `/opt/automation/agents/openclaw/compose`
  - `/opt/automation/agents/openclaw/config`
  - `/opt/automation/agents/openclaw/state`
  - `/opt/automation/agents/openclaw/logs`
  - `/etc/davlos/secrets/openclaw`
- estado validado del scaffold:
  - `STAGED_READY_FOR_IMAGE_AND_SECRETS`
- `openclaw.json.example` forma parte del bootstrap staged
- `openclaw.json` real sigue pendiente
- la consola puede mostrar el estado de la zona y el estado previsto de OpenClaw sin tocar producción

## deuda técnica explícita

- elegir imagen/build revisado de OpenClaw
- materializar secretos reales fuera del workspace
- convertir `openclaw.json.example` en `openclaw.json` validado contra la imagen elegida
- levantar `agents_net`
- ejecutar prechecks previos al deploy
- validar logs/health/runtime real

## siguiente hito técnico

Cerrar el tramo de inferencia/gateway para el primer arranque y dejar el runtime listo para predeploy sin introducir todavía `docker compose up`.
