# OPENCLAW Phase 12 Telegram Runtime Final

Fecha: 2026-04-01  
Rama: `codex/openclaw-console-readonly`

## objetivo

Cerrar el bot Telegram de OpenClaw como runtime persistente y presentable en el VPS, con secreto fuera del repo, arranque claro, logs visibles, rollback simple y validación operativa mínima.

## artefactos host-side instalados

- unit `systemd`: `/etc/systemd/system/openclaw-telegram-bot.service`
- secreto runtime: `/etc/davlos/secrets/openclaw/telegram-bot.env`
- policy viva: `/opt/automation/agents/openclaw/broker/restricted_operator_policy.json`
- directorios runtime:
  - `/opt/automation/agents/openclaw/broker`
  - `/opt/automation/agents/openclaw/broker/audit`
  - `/opt/automation/agents/openclaw/broker/state`
  - `/opt/automation/agents/openclaw/dropzone`

## decisiones

### 1. mantener `systemd`

No se introdujo otra arquitectura. Se reutilizó:

- `templates/openclaw/openclaw-telegram-bot.service`
- `scripts/agents/openclaw/restricted_operator/run_telegram_bot.sh`

### 2. mover el secreto fuera del repo

Se instaló el env runtime en:

- `/etc/davlos/secrets/openclaw/telegram-bot.env`

No se expuso el token en consola, docs ni cambios versionados.

### 3. promover policy viva host-side

Se generó la policy viva final bajo:

- `/opt/automation/agents/openclaw/broker/restricted_operator_policy.json`

Ajustes aplicados:

- `telegram.enabled=true`
- `allowed_chats["603178255"] -> david_admin`
- `allowed_users["603178255"] -> david_admin`
- `david_admin` con rol `admin`
- rutas de audit/state/offset/runtime_status bajo `/opt/automation/agents/openclaw/broker/...`

## validaciones ejecutadas

### policy

```bash
python3 /opt/control-plane/scripts/agents/openclaw/restricted_operator/cli.py \
  --policy /opt/automation/agents/openclaw/broker/restricted_operator_policy.json validate
```

Resultado:

- `ok=true`

### servicio

Comprobaciones ejecutadas:

- `systemctl enable --now openclaw-telegram-bot.service`
- `systemctl status openclaw-telegram-bot.service --no-pager`
- `systemctl restart openclaw-telegram-bot.service`
- `journalctl -u openclaw-telegram-bot.service -n 30 --no-pager`

Resultado:

- servicio cargado y habilitado
- servicio activo tras arranque
- restart correcto
- logs de systemd limpios en el ciclo de start/stop/start

### Telegram

Validación real del canal ya conseguida en esta fase de trabajo:

- `/status`
- `/capabilities`
- `/audit_tail`
- `/execute action.health.general.v1`

Resultado:

- los comandos fueron aceptados para `david_admin`
- la auditoría dejó eventos `telegram_command_executed`
- `action.health.general.v1` ejecutó correctamente con checks `openclaw_ui=200` e `inference_gateway_healthz=200`

Después de instalar el servicio persistente se confirmó:

- el bot arrancó en `systemd`
- `telegram_runtime_status.json` del runtime host-side quedó en `state=running`
- el servicio quedó listo para consumir nuevos updates reales

En la ventana de instalación no entraron todavía nuevos comandos post-`systemd`, así que esa observación concreta queda pendiente de siguiente comprobación operativa.

### auditoría y estado runtime

Rutas observables:

- `/opt/automation/agents/openclaw/broker/audit/restricted_operator.jsonl`
- `/opt/automation/agents/openclaw/broker/state/telegram_runtime_status.json`

Resultado esperado de operación:

- `telegram_runtime_status.json` refleja `state=running`
- la auditoría crece cuando entran comandos reales

## riesgos residuales

- el bot sigue en polling simple; no hay webhook ni supervisión externa adicional
- el rate limiting sigue siendo en memoria
- la visibilidad detallada del runtime depende de `journalctl`, `telegram_runtime_status.json` y del audit log del broker
- el despliegue actual asume root para leer el secreto y escribir estado/auditoría

## conclusión

La fase queda cerrada:

- runtime persistente instalado
- secreto fuera del repo
- servicio operativo en `systemd`
- rollback sencillo
- validación real de Telegram ya conseguida

Siguiente foco recomendado:

- pulido de la DAVLOS VPN Console
