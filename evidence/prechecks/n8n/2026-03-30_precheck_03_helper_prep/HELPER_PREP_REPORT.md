# Preparación del helper root-owned readonly para auditoría n8n

## Resumen

Se ha preparado un paquete local de instalación manual para resolver el bloqueo de inspección de `n8n` con mínimo privilegio.

No se ha instalado nada en el host.
No se han cambiado permisos efectivos del sistema.
No se ha concedido acceso a `devops` al grupo `docker`.

## Artefactos preparados

- `davlos-n8n-audit-readonly.sh`
- `davlos-n8n-audit-readonly.sudoers`
- `INSTALL_HELPER_ROOT_MANUAL.md`
- `ROLLBACK_HELPER_ROOT_MANUAL.md`
- `RETRY_PRECHECKS_AFTER_HELPER.md`

## Decisiones de diseño

- helper previsto para `/usr/local/sbin/davlos-n8n-audit-readonly`
- helper pensado para ser `root:root`
- solo dos subcomandos permitidos:
  - `docker_readonly`
  - `inventory_minimum`
- rutas absolutas a binarios críticos
- rechazo explícito de argumentos no permitidos
- salida saneada de entorno:
  - solo claves, nunca valores

## Riesgo residual principal

El helper resuelve el acceso restringido, pero los scripts publicados `30` y `40` todavía no están adaptados para consumirlo directamente.

Eso significa que, después de instalar el helper, la vía más segura de reintento inicial es ejecutar el helper directamente y guardar la salida en los archivos de evidencia equivalentes.

## Recomendación

1. revisar el helper y el sudoers
2. instalar manualmente como root
3. validar con `sudo -n -l`
4. ejecutar el helper directamente para cerrar la auditoría bloqueada
5. en una iteración posterior, adaptar los scripts publicados para usar ese backend restringido
