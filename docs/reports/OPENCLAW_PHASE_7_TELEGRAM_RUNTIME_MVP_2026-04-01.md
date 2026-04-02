# OPENCLAW PHASE 7 TELEGRAM RUNTIME MVP

## alcance

Fase 7 centrada en endurecimiento y despliegue operativo del canal Telegram privado de OpenClaw dentro del VPS.

Fuera de alcance:

- chat web
- autenticación remota compleja
- refactor del broker

## arquitectura runtime

Se mantiene la separación:

- Telegram como canal
- `operator_auth` como autorización real
- `RestrictedOperatorBroker` como ejecución real

Runtime elegido:

- wrapper Bash pequeño
- unit file de systemd de ejemplo
- token en fichero root-owned fuera del repo

## hardening aplicado

- validación de longitud máxima de comando
- rechazo de comandos multilinea
- límite básico de cantidad/tamaño de parámetros
- rate limiting simple por chat
- backoff exponencial ante fallos de polling
- logging operativo por stdout/stderr para journal
- `runtime_status.json` para observabilidad mínima
- no exposición del token en logs ni en repo

## runtime files

- `scripts/agents/openclaw/restricted_operator/run_telegram_bot.sh`
- `templates/openclaw/openclaw-telegram-bot.service`
- `templates/openclaw/telegram-bot.env.example`

## validaciones

- suite del broker y Telegram ampliada
- `telegram_bot.py --help`
- validación de policy con el bloque Telegram
- wrapper ejecutable

## observabilidad

Fuentes mínimas:

- `systemctl status openclaw-telegram-bot.service`
- `journalctl -u openclaw-telegram-bot.service`
- `telegram_runtime_status.json`
- audit log del broker

## riesgos residuales

- rate limiting en memoria y no persistente
- polling simple sin webhook
- no hay monitorización externa adicional

## decisión

`GO` para operación MVP real del canal Telegram privado en el VPS, manteniendo una base limpia para hardening adicional o para evaluar más adelante un canal web.
