# Operator Identity Auth MVP

## objetivo

Añadir una capa mínima y local de identidad/autorización para que la gestión de capacidades OpenClaw no dependa solo de un `actor` textual libre.

## modelo elegido

La identidad de operador vive dentro de la policy del restricted operator, en el bloque `operator_auth`.

Elementos:

- `roles`: mapa pequeño de permisos lógicos
- `operators`: allowlist explícita por `operator_id`
- `operator_id`: identificador estable usado por consola, CLI y auditoría

Roles del MVP:

- `viewer`: solo `policy.read`
- `operator`: `policy.read` y `policy.mutate`
- `admin`: `policy.read` y `policy.mutate`

En esta fase `operator` y `admin` tienen el mismo alcance práctico. La distinción queda preparada para futuras fases sin añadir complejidad ahora.

## operaciones protegidas

Requieren `policy.mutate`:

- `enable`
- `disable`
- `set-ttl`
- `clear-ttl`
- `reset-one-shot`
- `consume-one-shot`

No requieren autorización de mutación:

- `show`
- `audit-tail`
- `validate`

## flujo operativo

1. La consola resuelve un `operator_id`.
2. La CLI carga la policy viva.
3. La CLI valida el `operator_id` en `operator_auth`.
4. Si el operador tiene `policy.mutate`, aplica el cambio.
5. Si no lo tiene, rechaza la operación y la audita.

## auditoría

Las mutaciones y rechazos de autorización incluyen:

- `operator_id`
- `operator_role` cuando la autorización fue válida
- `authorized`
- `action_id`
- `reason`
- timestamp

Evento nuevo relevante:

- `operator_authorization_rejected`

## degradación

Si el operador no está autorizado:

- no se modifica la policy viva
- la consola muestra un mensaje corto
- el resto del modo readonly sigue funcionando

## límites

- no hay autenticación fuerte remota
- no hay secretos, tokens ni servicios externos
- la identidad sigue siendo local y declarativa
- no se gestiona todavía alta/baja dinámica de operadores desde la consola

## preparado para la siguiente fase

Esta base ya permite que un canal externo futuro entregue un `operator_id` validable contra una capa central antes de abrir o cerrar capacidades.
