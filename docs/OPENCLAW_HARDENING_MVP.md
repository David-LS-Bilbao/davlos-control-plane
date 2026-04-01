# OpenClaw Hardening MVP

## objetivo

Consolidar el estado operativo de OpenClaw, broker y Telegram antes de abrir más superficie.

## clasificación de cambios locales

### absorbidos en esta fase

- runtime Telegram:
  - `run_telegram_bot.sh`
  - `openclaw-telegram-bot.service`
  - `telegram-bot.env.example`
  - `TELEGRAM_OPENCLAW_RUNTIME_MVP.md`
- endurecimiento Telegram:
  - rate limiting simple
  - runtime status file
  - backoff de polling
  - rechazo de `edited_message`
  - validación de tamaño de comandos y parámetros
- policy/documentación de roles y permisos

### dejados fuera

- `evidence/prechecks/n8n/...`
- `scripts/prechecks/n8n/...`
- `templates/inference-gateway/`

Esos cambios no forman parte del hardening actual de OpenClaw y no deben mezclarse sin una intervención específica.

## endurecimientos aplicados

### telegram

- canal privado con allowlist
- rate limiting pragmático por usuario, con fallback funcional
- rechazo de mensajes editados
- runtime status observable
- token fuera del repo
- unit file con restricciones de systemd

### roles

- `viewer`: lectura básica
- `operator`: lectura y ejecución de acciones no sensibles
- `admin`: además `operator.audit` y `operator.control`

Decisión práctica:

- `/audit_tail` por Telegram queda reservado a `admin`
- acciones con `permission=operator.control` quedan reservadas a `admin`

### broker/policy

- la policy sigue siendo la fuente de control
- el broker sigue siendo el único plano de ejecución
- Telegram sigue siendo solo un adaptador

## digest pin

No se aplica pin por digest automáticamente en esta fase para no invadir runtime real sin verificación operativa.

Contrato propuesto:

1. resolver digest de imagen en una intervención deliberada
2. fijarlo en compose/runtime documentado
3. registrar fecha, digest y motivo del refresh

## ufw drift

El drift de UFW sigue siendo deuda operativa conocida.

Contrato:

- no se reabre el cambio de firewall en esta fase
- se mantiene documentado que la configuración declarada y el runtime deben normalizarse en una intervención acotada

## agents_net egress allowlist

Primer paso real en esta fase: no tocar reglas activas, pero dejar el contrato preparado.

Objetivo siguiente:

- definir destinos explícitos permitidos para OpenClaw
- aplicar allowlist mínima sin romper reachability a `inference-gateway`

## riesgos residuales

- rate limiting en memoria, no persistente
- polling Telegram simple
- pin por digest pendiente de aplicación deliberada
- normalización de UFW pendiente
- allowlist de egress pendiente de materialización
