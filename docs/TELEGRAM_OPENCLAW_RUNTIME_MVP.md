# Telegram OpenClaw Runtime MVP

## objetivo

Dejar el bot Telegram de OpenClaw listo para operación MVP real en el VPS con:

- token fuera del repo
- arranque/parada claros
- logs por journal
- estado runtime observable
- rollback sencillo

## arquitectura runtime elegida

Se usa:

- `run_telegram_bot.sh` como wrapper pequeño de arranque
- `openclaw-telegram-bot.service` como unit file de systemd de ejemplo
- polling largo contra Telegram

El wrapper:

- valida que la policy exista
- valida que el env file exista
- carga el token desde un fichero root-owned
- ejecuta `telegram_bot.py`

## ficheros

- `scripts/agents/openclaw/restricted_operator/run_telegram_bot.sh`
- `templates/openclaw/openclaw-telegram-bot.service`
- `templates/openclaw/telegram-bot.env.example`

## configuración

### env file

Ruta sugerida:

- `/etc/davlos/secrets/openclaw/telegram-bot.env`

Contenido mínimo:

- `OPENCLAW_TELEGRAM_BOT_TOKEN=...`

No meter este fichero en git.

### policy

La policy viva debe definir:

- `telegram.enabled=true`
- `telegram.allowed_chats` y/o `telegram.allowed_users`
- `telegram.offset_store_path`
- `telegram.runtime_status_path`
- `telegram.rate_limit_window_seconds`
- `telegram.rate_limit_max_requests`

## despliegue con systemd

1. Copiar el env file root-owned:

```bash
install -m 0600 -o root -g root /tmp/telegram-bot.env /etc/davlos/secrets/openclaw/telegram-bot.env
```

2. Instalar la unit:

```bash
install -m 0644 -o root -g root /opt/control-plane/templates/openclaw/openclaw-telegram-bot.service /etc/systemd/system/openclaw-telegram-bot.service
systemctl daemon-reload
```

3. Habilitar y arrancar:

```bash
systemctl enable --now openclaw-telegram-bot.service
```

## operación

### estado

```bash
systemctl status openclaw-telegram-bot.service --no-pager
```

### logs

```bash
journalctl -u openclaw-telegram-bot.service -n 50 --no-pager
```

### restart

```bash
systemctl restart openclaw-telegram-bot.service
```

### stop

```bash
systemctl stop openclaw-telegram-bot.service
```

## observabilidad mínima

El bot mantiene:

- `telegram_offset.json`
- `telegram_runtime_status.json`

El runtime status indica al menos:

- `state`
- `ts`
- `next_offset`
- `last_update_id` cuando aplica
- `last_error` cuando entra en degradado

## validación mínima

1. comprobar `systemctl status`
2. comprobar `journalctl`
3. comprobar que `telegram_runtime_status.json` existe
4. enviar `/help` o `/status` desde un chat allowlisted
5. comprobar auditoría del broker

## hardening MVP aplicado

- token fuera del repo
- unit con `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `PrivateTmp=true`
- `UMask=0077`
- `ProtectKernelTunables=true`
- `ProtectControlGroups=true`
- `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`
- `ReadWritePaths` limitados a broker state/dropzone
- rate limiting simple por usuario, con fallback funcional
- backoff exponencial ante fallos de polling
- validación de tamaño de comando y parámetros
- `edited_message` ignorado por completo

## separación de roles en Telegram

- `operator`: `/status`, `/capabilities` y ejecución de acciones permitidas
- `admin`: además `/audit_tail` y acciones con `operator.control`

## rollback

```bash
systemctl disable --now openclaw-telegram-bot.service
rm -f /etc/systemd/system/openclaw-telegram-bot.service
systemctl daemon-reload
```

Opcional:

- dejar `telegram.enabled=false` en la policy viva
- conservar auditoría y estado para análisis

## límites

- polling simple, no webhook
- sin supervisión externa adicional
- rate limiting en memoria, suficiente para MVP pero no persistente
