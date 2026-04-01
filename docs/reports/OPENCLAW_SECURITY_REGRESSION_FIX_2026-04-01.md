# OPENCLAW SECURITY REGRESSION FIX

## alcance

Parche correctivo corto sobre tres bloqueadores confirmados:

1. `enable --ttl-minutes` con mutación parcial
2. autorización de mutaciones sin respetar el permiso efectivo de la acción
3. re-ejecución por `edited_message` en Telegram

## correcciones aplicadas

### 1. TTL atómico

Se eliminó la composición insegura `enable` + `set-ttl` en dos pasos.

Ahora `enable_with_optional_ttl`:

- valida primero permisos y TTL
- calcula la expiración
- persiste `enabled` y `expires_at` en una sola mutación lógica de policy layer

Resultado:

- o se aplica `enable + ttl` completo
- o no se persiste ningún cambio

### 2. autorización por permiso efectivo

Las mutaciones ya no validan solo `policy.mutate`.

Ahora exigen:

- `policy.mutate`
- y el `permission` declarado por la acción objetivo

Ejemplo:

- `action.openclaw.restart.v1` requiere `operator.control`
- un operador sin `operator.control` ya no puede habilitarla, darle TTL ni resetearla

### 3. Telegram y edited_message

El adaptador Telegram ya no procesa `edited_message`.

Solo se aceptan mensajes nuevos en `message`. Las ediciones se ignoran por completo para evitar re-ejecución accidental.

## validaciones de regresión

- TTL inválido no deja la acción habilitada
- enable con TTL válido aplica `enabled + expires_at`
- operador normal no puede habilitar acción de control
- admin sí puede habilitar acción de control
- `edited_message` no dispara ejecución ni respuesta

## decisión

Parche aplicado y listo para dejar la fase aceptable desde el punto de vista de estos tres bloqueadores.
