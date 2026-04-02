# DAVLOS VPN Console Polish MVP

## objetivo

Pulir la DAVLOS VPN Console MVP como herramienta de operación sin rehacer su arquitectura.

## fricciones detectadas

- el submenú de capacidades mostraba JSON crudo poco legible
- el operador no distinguía rápido entre lectura y mutación
- los errores de mutación eran demasiado genéricos
- `expires_at`, `one_shot` y `consumed` no quedaban visibles de un vistazo

## mejoras aplicadas

### capacidades OpenClaw

- salida `console` desde la CLI para estado efectivo
- resumen inicial con:
  - total
  - enabled
  - disabled
  - expired
  - consumed
- cada acción muestra:
  - `action_id`
  - `status`
  - `mode`
  - `allowed`
  - `permission`
  - `expires_at` si aplica
  - `one_shot` y `consumed` si aplica
  - `reason` si existe

### auditoría

- salida `console` desde la CLI para eventos recientes
- visibilidad directa de:
  - `event`
  - `action_id`
  - `ok`
  - `operator_id`
  - `operator_role`
  - `code` o `error` cuando aplica

### navegación y copy

- submenú de capacidades con etiquetas `[readonly]` y `[mutating]`
- ayuda de consola más clara sobre qué puede verse y qué puede cambiarse
- mensajes de error más útiles cuando falla una mutación

## principio mantenido

La consola no duplica la lógica del broker/policy.

Solo consume:

- `cli.py show --format console`
- `cli.py audit-tail --format console`
- comandos mutantes existentes

## límites

- sigue siendo una consola MVP de terminal
- no añade nuevas capacidades
- no cambia permisos reales, solo los hace más visibles
