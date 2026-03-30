# Runbook de preparación de migración n8n

## Objetivo

Definir la preparación documental mínima requerida antes de cualquier futura migración operativa de `n8n` desde su estado actual dependiente de `/root` hacia la ruta objetivo deseada `/opt/automation/n8n`.

Este runbook no ejecuta cambios.
Este runbook no autoriza una migración.
Este runbook no contiene secretos ni valores sensibles.

## Estado actual confirmado

Dependencias operativas confirmadas de `n8n`:

- `/root/docker-compose.yaml`
- `/root/n8n.env`
- `/root/local-files`
- volumen Docker `root_n8n_data`

Estado adicional confirmado:

- `n8n` sigue dependiendo operativamente de `/root`.
- El objetivo futuro deseado es llevar `n8n` a `/opt/automation/n8n`.
- En esta fase no se ejecutan migraciones ni cambios sobre servicios.

## Dependencias actuales

Dependencias confirmadas:

- definición compose en `/root/docker-compose.yaml`
- variables de entorno en `/root/n8n.env`
- bind mount de archivos en `/root/local-files`
- persistencia Docker en volumen `root_n8n_data`

Dependencias probables pero no confirmadas completamente en este runbook:

- parámetros adicionales de red, restart policy o labels definidos en el compose
- dependencia de secretos externos no documentados en este repositorio
- dependencia funcional del contenido almacenado en `/root/local-files`

Si esos detalles se necesitan para ejecución futura, deberán verificarse con evidencia específica antes de mover nada.

## Riesgos principales

- riesgo de indisponibilidad de `n8n` si se altera la definición actual sin preservar compose, entorno, mounts y persistencia
- riesgo de pérdida de configuración o historial si no se respalda correctamente el volumen `root_n8n_data`
- riesgo de rotura funcional si `/root/local-files` contiene archivos usados por workflows activos
- riesgo de migración incompleta si el contenido real de `/root/n8n.env` no se trata como dependencia crítica
- riesgo documental si se asume que `/opt/automation/n8n` ya es operativo cuando hoy solo es una ruta objetivo

## Prechecks obligatorios

Antes de cualquier ejecución futura, deben validarse como mínimo los siguientes puntos:

- confirmar que el servicio activo sigue correspondiendo a la definición de `/root/docker-compose.yaml`
- confirmar que `/root/n8n.env` sigue siendo la fuente real de variables de entorno
- confirmar que `/root/local-files` sigue siendo un mount activo y necesario
- confirmar que el volumen `root_n8n_data` es la persistencia efectiva de `n8n`
- confirmar qué artefactos deben conservarse para rollback
- confirmar ventana operativa y criterio de impacto aceptable

Falta evidencia en este repositorio sobre:

- tamaño de datos a respaldar
- número de workflows activos
- dependencia exacta de credenciales, webhooks o integraciones externas
- procedimiento de backup ya validado mediante restore

## Backup mínimo requerido antes de mover nada

Antes de cualquier migración futura, debe existir al menos respaldo verificable de:

- el archivo de definición `docker-compose` actualmente usado por `n8n`
- el archivo de entorno asociado, sin exponer su contenido en este repositorio
- el contenido de `/root/local-files`
- el contenido persistente del volumen Docker `root_n8n_data`

Requisitos mínimos del backup:

- copia íntegra y fechada
- ubicación de resguardo identificable
- validación de integridad básica
- procedimiento de restauración documentado

No hay evidencia confirmada en este repositorio de que ese backup exista hoy ni de que haya sido probado por restore.

## Rollback conceptual

Si una futura migración no valida correctamente, el rollback conceptual debe permitir volver al último estado operativo conocido de `n8n` usando:

- la definición compose previamente activa
- el entorno previamente activo
- el bind mount previamente activo
- la persistencia previa del volumen

El rollback debe priorizar restaurar operatividad conocida, no completar la reordenación del layout.

Falta evidencia en este repositorio sobre:

- tiempo objetivo de recuperación
- procedimiento exacto de restauración
- validación restaurada tras rollback

## Criterios de validación post-migración

Una futura migración solo debería considerarse válida si, como mínimo:

- `n8n` inicia correctamente con su configuración esperada
- la persistencia queda accesible e íntegra
- los archivos requeridos desde el mount funcional equivalente a `/root/local-files` siguen disponibles
- los workflows esperados están presentes
- las integraciones críticas responden como se espera
- el acceso operativo definido para el servicio sigue siendo consistente con la arquitectura del VPS

Falta evidencia para fijar en este documento:

- lista cerrada de workflows críticos
- lista cerrada de integraciones críticas
- pruebas funcionales concretas por flujo

## Qué no debe hacerse todavía

- no mover `n8n` a `/opt/automation/n8n`
- no editar la definición operativa actual en `/root/docker-compose.yaml`
- no modificar `/root/n8n.env`
- no mover ni limpiar `/root/local-files`
- no alterar el volumen `root_n8n_data`
- no asumir equivalencia entre layout objetivo y estado real
- no ejecutar cambios sin backup documentado y rollback definido

## Checklist previa a ejecución

- [ ] Fuente de verdad operativa de `n8n` reconfirmada
- [ ] Dependencias activas reconfirmadas
- [ ] Backup mínimo completo preparado
- [ ] Ubicación del backup documentada
- [ ] Criterio de rollback documentado
- [ ] Validaciones funcionales mínimas definidas
- [ ] Alcance exacto del cambio aprobado
- [ ] Ventana de intervención aprobada
- [ ] Evidencia previa y posterior preparada en el control-plane

## Referencias

- `docs/N8N_FUNCTIONAL_DEPENDENCIES.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`
- `docs/ARCHITECTURE.md`
- `docs/LAYOUT_PHASE_2_PROPOSAL.md`
- `evidence/FASE_1_CIERRE.md`
- `inventory/INITIAL_INVENTORY.md`
