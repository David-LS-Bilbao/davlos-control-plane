# Plan de ventana de migración n8n fuera de /root

## 1. Objetivo

Definir la futura ventana real de migración de `n8n` fuera de `/root` hacia el layout objetivo del VPS DAVLOS, sin cambiar todavía producción en esta tarea.

El objetivo operativo de la intervención será:

- mover la definición operativa fuera de `/root`
- mover el fichero de entorno fuera de `/root`
- mover el bind mount de archivos fuera de `/root`
- mantener la persistencia Docker existente
- mantener la red actual
- mantener el puerto actual
- mantener el acceso actual detrás de NPM

Ruta objetivo exacta propuesta:

- `/opt/automation/n8n`

Subestructura objetivo recomendada para esta intervención:

- `/opt/automation/n8n/compose/docker-compose.yaml`
- `/opt/automation/n8n/env/n8n.env`
- `/opt/automation/n8n/local-files/`

En esta intervención no se propone renombrar el volumen Docker `root_n8n_data`.
La opción más prudente es conservarlo tal como está para reducir riesgo.

## 2. Estado previo confirmado

Estado operativo confirmado:

- `n8n` sigue dependiendo de:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`
  - red Docker `verity_network`
- `n8n` está publicado en `127.0.0.1:5678`
- el acceso está detrás de NPM
- el contenedor actual es `root-n8n-1`
- la política de reinicio observada es `unless-stopped`
- el bind mount actual observado es:
  - `/root/local-files -> /files`
- la persistencia observada es:
  - volumen `root_n8n_data -> /home/node/.n8n`

Hechos adicionales confirmados:

- el helper readonly ya permitió inspección segura
- existe backup mínimo real en:
  - `/opt/backups/n8n/2026-03-30_pre_migration_01`
- existe rollback mínimo documentado

## 3. Alcance exacto

Esta intervención debe cubrir únicamente:

- creación de las rutas objetivo bajo `/opt/automation/n8n`
- copia controlada de `docker-compose.yaml` a la nueva ruta
- copia controlada de `n8n.env` a la nueva ruta
- copia controlada de `local-files` a la nueva ruta
- ajuste del compose objetivo para apuntar a las nuevas rutas fuera de `/root`
- recreación controlada del servicio `n8n` usando:
  - mismo puerto `127.0.0.1:5678`
  - misma red `verity_network`
  - mismo volumen `root_n8n_data`
  - mismo comportamiento de publicación actual

Esta intervención no debe cubrir:

- cambio de volumen a otro nombre
- migración de base de datos
- cambio de red
- cambio de puerto
- cambio de proxy/NPM
- limpieza o borrado de artefactos bajo `/root`
- rediseño funcional de workflows

## 4. Precondiciones

Antes de abrir la ventana deben cumplirse todas:

- [ ] Backup mínimo real verificado en `/opt/backups/n8n/2026-03-30_pre_migration_01`
- [ ] Integridad básica del backup confirmada
- [ ] Acceso root operativo disponible para la intervención
- [ ] Compose activo actual reconfirmado
- [ ] Rutas activas actuales reconfirmadas
- [ ] Salida readonly de Docker capturada como evidencia inmediatamente antes de la intervención
- [ ] Espacio suficiente en `/opt` para copiar `local-files`
- [ ] Ventana aprobada
- [ ] Criterio de abortar aceptado
- [ ] Criterio de rollback aceptado

Precondiciones técnicas específicas:

- [ ] `verity_network` existe y sigue siendo la red del contenedor
- [ ] `root_n8n_data` existe y sigue siendo el volumen de persistencia en uso
- [ ] `n8n` responde en `127.0.0.1:5678` antes de tocar nada
- [ ] NPM responde localmente antes de tocar nada
- [ ] El compose objetivo ha sido revisado sin exponer secretos

## 5. Secuencia de intervención

### Fase A. Captura previa inmediata

1. Capturar evidencia readonly justo antes del cambio:
   - estado del contenedor
   - mounts
   - red
   - volume inspect
   - claves de entorno, no valores
2. Verificar respuesta local:
   - `curl -I http://127.0.0.1:5678`
   - `curl -I http://127.0.0.1:81`

### Fase B. Preparación de rutas objetivo

3. Crear rutas objetivo:
   - `/opt/automation/n8n/compose/`
   - `/opt/automation/n8n/env/`
   - `/opt/automation/n8n/local-files/`
4. Asignar ownership y permisos coherentes con el modo de operación esperado.

### Fase C. Copia de artefactos

5. Copiar el compose actual a:
   - `/opt/automation/n8n/compose/docker-compose.yaml`
6. Copiar el env actual a:
   - `/opt/automation/n8n/env/n8n.env`
7. Copiar `local-files` actual a:
   - `/opt/automation/n8n/local-files/`
8. Validar que la copia de `local-files` es consistente por tamaño y conteo básico.

### Fase D. Preparación del compose objetivo

9. Revisar el compose copiado y ajustar únicamente las rutas bind mount necesarias para apuntar a:
   - `/opt/automation/n8n/env/n8n.env`
   - `/opt/automation/n8n/local-files`
10. Mantener sin cambio:
   - imagen
   - puerto `127.0.0.1:5678`
   - red `verity_network`
   - volumen `root_n8n_data`
   - restart policy observada

### Fase E. Cambio controlado

11. Detener el servicio actual de `n8n`.
12. Levantar `n8n` usando el compose objetivo bajo `/opt/automation/n8n/compose/`.
13. Confirmar que el nuevo contenedor arranca correctamente.

### Fase F. Validación inmediata

14. Validar puerto local `127.0.0.1:5678`.
15. Validar que el contenedor sigue unido a `verity_network`.
16. Validar que el volumen `root_n8n_data` sigue montado.
17. Validar que el bind mount ahora apunta a `/opt/automation/n8n/local-files`.
18. Validar presencia básica de workflows esperados.
19. Validar que NPM sigue respondiendo y que la topología de acceso no ha cambiado.

### Fase G. Cierre de ventana

20. Si todo valida, dejar evidencia final en el control-plane.
21. No borrar artefactos de `/root` en esta misma intervención.

## 6. Validación inmediata post-cambio

Validaciones técnicas mínimas:

- `n8n` responde localmente en `127.0.0.1:5678`
- el contenedor está `running` y estable
- el contenedor usa `verity_network`
- el volumen `root_n8n_data` sigue presente y montado
- el bind mount de archivos apunta a la nueva ruta bajo `/opt/automation/n8n/local-files`
- el puerto publicado sigue siendo `127.0.0.1:5678`

Validaciones funcionales mínimas:

- workflows esperados presentes
- no hay evidencia inmediata de pérdida de estado
- las funciones dependientes de archivos no fallan de forma evidente
- los webhooks esperados siguen siendo coherentes con el estado previo

Validaciones de acceso:

- NPM sigue operativo
- no se ha alterado la topología pública

## 7. Criterios de abortar

Debe abortarse la intervención antes o durante el cambio si ocurre cualquiera de estas condiciones:

- el backup no resulta verificable
- la copia de `local-files` no cuadra en tamaño o estructura básica
- el compose objetivo no puede validarse con seguridad
- la red `verity_network` no está disponible
- el volumen `root_n8n_data` no aparece como esperado
- el nuevo contenedor no arranca
- `127.0.0.1:5678` no responde tras el cambio
- el servicio muestra mounts distintos a los previstos
- la validación mínima indica pérdida evidente de workflows o de persistencia

## 8. Rollback exacto

Si la validación falla, la secuencia exacta de rollback debe ser:

1. detener el contenedor o stack levantado desde `/opt/automation/n8n/compose/`
2. restaurar el compose previo a `/root/docker-compose.yaml` desde el backup
3. restaurar el env previo a `/root/n8n.env` desde el backup
4. restaurar `local-files` previo a `/root/local-files` desde el backup
5. restaurar el contenido del volumen `root_n8n_data` desde el backup si hubo alteración o duda razonable sobre integridad
6. levantar de nuevo `n8n` con la definición previa en `/root/docker-compose.yaml`
7. revalidar:
   - `127.0.0.1:5678`
   - red `verity_network`
   - mounts esperados
   - presencia de workflows esperados
   - NPM operativo

Regla importante:

- en rollback se prioriza volver al último estado operativo conocido, no completar la reordenación del layout

## 9. Criterios de éxito

La ventana solo debe considerarse exitosa si:

- `n8n` queda operativo y estable
- `n8n` deja de depender operativamente de rutas bajo `/root` para compose, env y local-files
- la persistencia sigue usando `root_n8n_data` sin pérdida observable
- la red `verity_network` se conserva
- el puerto `127.0.0.1:5678` se conserva
- NPM y la topología de acceso siguen coherentes
- no hay señales inmediatas de degradación funcional

## 10. Riesgos residuales

- el volumen sigue manteniendo el nombre histórico `root_n8n_data`, lo que deja deuda de nomenclatura aunque reduzca riesgo técnico
- la lista cerrada de workflows críticos sigue incompleta
- la dependencia funcional exacta de `local-files` sigue siendo sensible durante el cambio
- cualquier diferencia no documentada en el compose real puede impactar la recreación
- si el contenedor actual usa parámetros adicionales no reflejados en el compose objetivo, podrían aparecer diferencias tras el recreado

## 11. Checklist final de ejecución

- [ ] Ventana aprobada
- [ ] Backup mínimo real confirmado
- [ ] Rollback aceptado
- [ ] Evidencia readonly previa capturada
- [ ] Rutas objetivo creadas bajo `/opt/automation/n8n`
- [ ] Compose copiado y revisado
- [ ] Env copiado y revisado sin exponer secretos
- [ ] `local-files` copiado y validado
- [ ] Compose objetivo ajustado solo en rutas necesarias
- [ ] Red `verity_network` confirmada
- [ ] Volumen `root_n8n_data` confirmado
- [ ] Servicio actual detenido de forma controlada
- [ ] Servicio nuevo levantado desde `/opt/automation/n8n`
- [ ] Validación técnica inmediata superada
- [ ] Validación funcional mínima superada
- [ ] Evidencia posterior guardada
- [ ] Cierre como éxito o rollback documentado
