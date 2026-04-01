# OPENCLAW PHASE 8 HARDENING MVP

## alcance

Fase 8 centrada en endurecimiento operativo del sistema actual:

- OpenClaw
- restricted operator broker
- canal Telegram

Sin añadir canales nuevos.

## cambios absorbidos

Se absorben los cambios locales útiles de runtime Telegram:

- wrapper de arranque
- unit file de systemd de ejemplo
- plantilla de env sin secreto
- documentación runtime

## cambios dejados fuera

No se mezclan en esta fase:

- inventario readonly heredado de n8n
- scripts readonly heredados de n8n
- plantillas heredadas de inference-gateway

## endurecimientos aplicados

### telegram

- rate limiting simple y pragmático
- rechazo explícito de `edited_message`
- runtime status file
- backoff ante errores de polling
- validación de tamaño/forma de comandos
- logs operativos limpios para journal

### separación de roles

- `operator` no obtiene `operator.audit`
- `admin` sí obtiene `operator.audit` y `operator.control`
- `/audit_tail` por Telegram queda restringido a `admin`

### runtime service

- wrapper Bash pequeño
- unit file con:
  - `NoNewPrivileges=true`
  - `ProtectSystem=strict`
  - `ProtectHome=true`
  - `PrivateTmp=true`
  - `UMask=0077`
  - `ProtectKernelTunables=true`
  - `ProtectControlGroups=true`
  - `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`

## validaciones

- tests del restricted operator
- validación de policy
- ayuda del bot Telegram
- cobertura de rate limiting y control de roles

## deuda residual formalizada

- pin por digest pendiente de aplicación deliberada
- normalización de drift UFW pendiente
- allowlist real de egress `agents_net` pendiente

## decisión

`GO` para mantener el sistema actual en operación MVP endurecida y decidir después si conviene avanzar a un canal web o a hardening adicional más profundo.
