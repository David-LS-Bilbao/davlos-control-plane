# OPENCLAW PHASE 6 TELEGRAM MVP

## alcance

Fase 6 centrada en un primer canal externo privado para OpenClaw usando Telegram.

Fuera de alcance:

- chat web
- menús conversacionales complejos
- autenticación remota fuerte
- ejecución arbitraria

## diseño aplicado

Se añadió un adaptador local por polling:

- Telegram -> allowlist chat/user -> `operator_id`
- `operator_id` -> `operator_auth`
- ejecución -> `RestrictedOperatorBroker`

Telegram queda como canal. No se duplican handlers ni lógica de policy.

## componentes

- `telegram_bot.py` como adaptador de canal
- config Telegram dentro de la policy viva
- template de env sin secretos reales para el token

## controles de seguridad

- allowlist explícita de `chat_id` y `user_id`
- mapeo a `operator_id` local
- autorización real contra permisos de la policy
- payload cerrado por acción en `/execute`
- auditoría de canal y de broker
- sin shell arbitraria

## comandos MVP

- `/help`
- `/status`
- `/capabilities`
- `/audit_tail`
- `/execute <action_id> [k=v ...]`

## validaciones

- tests unitarios ampliados para:
  - chat autorizado
  - chat no autorizado
  - `/execute` válido
  - rechazo de ejecución para operador con permisos insuficientes

## estado final

Existe una base real de canal Telegram privado que:

- consulta estado y capacidades
- ejecuta acciones del broker por ID
- respeta la allowlist de Telegram
- respeta la autorización local de operador

## riesgos residuales

- polling simple, no servicio productizado todavía
- token gestionado por env local fuera del repo
- comandos de Telegram todavía son deliberadamente austeros
- sin rate limiting específico en esta fase

## decisión

`GO` para una fase posterior de operación real por Telegram privado o para reutilizar el mismo contrato en un futuro chat web.
