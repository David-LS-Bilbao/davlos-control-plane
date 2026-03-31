# Fase 8 MVP: operador restringido

## objetivo

Definir una cuenta de operación limitada para usar la consola sin convertirla en cuenta administrativa general.

## usuario previsto

- usuario dedicado de operación, separado de `devops`
- pensado para ejecutar la consola y acciones permitidas, no para administrar el VPS completo

## limites de uso

- sin acceso general a secretos
- sin acceso libre a Docker
- sin acceso general a `/root`
- sin cambios de red o servicios salvo wrappers futuros muy acotados

## relacion con devops

- `devops` sigue siendo la cuenta administrativa real
- el operador restringido no sustituye a `devops`
- el operador restringido debe ser reversible y auditable

## sudo previsto

- preferencia por no dar sudo general
- si hiciera falta, solo comandos puntuales y readonly u operativos muy acotados

## plan reversible

- crear usuario
- asignar shell, grupo y rutas permitidas
- validar consola y límites
- retirar usuario y permisos si no convence el modelo

## validaciones futuras

- confirmar que la consola funciona con esa cuenta
- confirmar que no puede salir del perímetro previsto
- confirmar que `devops` conserva la administración real sin interferencias
