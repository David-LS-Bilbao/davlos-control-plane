# OPENCLAW PHASE 5 OPERATOR AUTH MVP

## alcance

Fase 5 centrada en identidad/autorización mínima del operador para la gestión de capacidades OpenClaw desde la DAVLOS VPN Console y la CLI del restricted operator.

Fuera de alcance:

- Telegram
- chat web
- autenticación remota fuerte
- OAuth o servicios externos

## diseño aplicado

Se añadió una allowlist local de operadores dentro de la policy viva del broker:

- `operator_auth.roles`
- `operator_auth.operators`

La validación queda centralizada en la CLI/policy layer. La consola solo resuelve un `operator_id` y delega la mutación a la CLI.

## decisiones

- mantener la solución local y versionable
- no crear un servicio de auth separado
- permitir readonly sin autorización de mutación
- exigir `policy.mutate` para cambios de capacidades

## cambios implementados

- validación central de operadores autorizados en `PolicyStore.authorize_operator`
- enriquecimiento de auditoría con `operator_id`, `operator_role` y `authorized`
- rechazo auditado de mutaciones no autorizadas con `operator_authorization_rejected`
- integración de la consola para pedir o resolver `operator_id` explícito antes de mutar
- actualización de la policy de ejemplo con roles `viewer/operator/admin`

## validaciones

- `python3 -m unittest tests.restricted_operator.test_broker`
- cobertura añadida para:
  - operador autorizado
  - operador no autorizado
  - operación readonly permitida
  - cambio bloqueado para viewer

## estado final

El control de capacidades ya no depende solo de un `actor` libre.

Solo operadores allowlisted con permiso `policy.mutate` pueden cambiar:

- `enabled`
- `disabled`
- `expires_at`
- `one_shot` consumido/reset

La consola sigue operativa en readonly aunque no exista autorización de mutación.

## riesgos residuales

- la identidad sigue siendo local y declarativa
- no existe prueba criptográfica de identidad
- la allowlist todavía se mantiene por fichero y no por UI

## decision

`GO` para una fase siguiente de canal externo o autenticación más fuerte, porque ya existe una capa mínima útil de identidad/autorización local y auditable.
