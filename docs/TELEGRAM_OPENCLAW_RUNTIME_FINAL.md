# Telegram OpenClaw Runtime Final

## objetivo

Cerrar el bot Telegram de OpenClaw como runtime persistente y operativo en el VPS sin mover secretos al repo ni alterar el boundary existente.

## estado final

Queda instalado como servicio `systemd`:

- unit: `/etc/systemd/system/openclaw-telegram-bot.service`
- env runtime: `/etc/davlos/secrets/openclaw/telegram-bot.env`
- policy viva: `/opt/automation/agents/openclaw/broker/restricted_operator_policy.json`
- helper readonly host-side: `/usr/local/sbin/davlos-openclaw-readonly`
- sudoers mínimo del helper: `/etc/sudoers.d/davlos-openclaw-readonly`

El modelo de seguridad no cambia:

- Telegram sigue siendo solo canal
- la autorización real sigue en `operator_auth`
- la ejecución real sigue en el broker restringido

## runtime host-side

### secreto

Ruta efectiva:

- `/etc/davlos/secrets/openclaw/telegram-bot.env`

Expectativa:

- root-owned
- modo `0600`
- fuera de git

Contenido mínimo esperado:

- `OPENCLAW_TELEGRAM_BOT_TOKEN=...`

### policy viva

Ruta efectiva:

- `/opt/automation/agents/openclaw/broker/restricted_operator_policy.json`

La policy viva deja:

- `telegram.enabled=true`
- `allowed_chats["603178255"] -> david_admin`
- `allowed_users["603178255"] -> david_admin`
- `david_admin` con rol `admin`

### estado y auditoría

Rutas efectivas:

- audit log: `/opt/automation/agents/openclaw/broker/audit/restricted_operator.jsonl`
- state store: `/opt/automation/agents/openclaw/broker/state/restricted_operator_state.json`
- telegram offset: `/opt/automation/agents/openclaw/broker/state/telegram_offset.json`
- telegram runtime status: `/opt/automation/agents/openclaw/broker/state/telegram_runtime_status.json`

## operación

### arrancar

```bash
systemctl enable --now openclaw-telegram-bot.service
```

### parar

```bash
systemctl stop openclaw-telegram-bot.service
```

### reiniciar

```bash
systemctl restart openclaw-telegram-bot.service
```

### estado

```bash
systemctl status openclaw-telegram-bot.service --no-pager
```

### logs

```bash
journalctl -u openclaw-telegram-bot.service -n 50 --no-pager
```

### observabilidad mínima

```bash
cat /opt/automation/agents/openclaw/broker/state/telegram_runtime_status.json
tail -n 20 /opt/automation/agents/openclaw/broker/audit/restricted_operator.jsonl
```

### observabilidad recomendada desde consola

```bash
bash /opt/control-plane/scripts/console/davlos-vpn-console.sh overview
bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-telegram
bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-capabilities-audit
bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-diagnostics
```

Si la sesión `devops` no puede leer directamente `/opt/automation/agents/openclaw/broker/state`, la consola usa el helper readonly para:

- `telegram_runtime_status.json`
- auditoría reciente del broker
- estado efectivo de capacidades

La observabilidad ampliada vía helper sigue siendo cerrada:

- usa modos concretos del helper, no rutas arbitrarias
- para logs recientes opera sobre una allowlist fija de units
- no equivale a acceso general a `journald`

## validación final esperada

Comandos ya validados en Telegram:

- `/status`
- `/capabilities`
- `/audit_tail`
- `/execute action.health.general.v1`

Validación mínima después de cambios operativos:

1. `systemctl status`
2. `systemctl restart`
3. `journalctl`
4. comprobar avance de `telegram_runtime_status.json`
5. enviar `/status`, `/capabilities` y `/execute action.health.general.v1`
6. revisar auditoría del broker

## rollback

Parada rápida:

```bash
systemctl disable --now openclaw-telegram-bot.service
```

Retirada de la unit:

```bash
rm -f /etc/systemd/system/openclaw-telegram-bot.service
systemctl daemon-reload
```

Rollback lógico adicional, si hiciera falta:

- dejar `telegram.enabled=false` en la policy viva
- conservar `audit` y `state` para análisis
- mantener el secreto fuera del repo aunque el servicio quede parado

## límites conocidos

- polling largo, no webhook
- el secreto vive solo en runtime host-side
- la separación de permisos depende de `operator_auth` y de la policy viva
- no se han añadido nuevas acciones ni nuevos canales
- la observabilidad detallada sin root depende del helper readonly o de permisos equivalentes de lectura
