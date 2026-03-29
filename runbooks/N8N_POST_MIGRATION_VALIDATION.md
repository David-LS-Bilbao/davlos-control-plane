# Validación funcional mínima post-migración de n8n

## Objetivo

Definir una validación funcional mínima y prudente para usar después de una futura migración operativa de `n8n`.

Este documento no ejecuta cambios.
Este documento no autoriza una migración.
Este documento no contiene secretos ni valores sensibles.

## Alcance

Este anexo cubre únicamente criterios mínimos de validación técnica y funcional posteriores a una futura migración de `n8n` hacia el layout objetivo deseado.

No cubre:

- el procedimiento de migración
- el procedimiento detallado de backup
- el procedimiento detallado de rollback
- validaciones exhaustivas por cada workflow o integración

Si se necesita una validación más profunda, deberá construirse con evidencia adicional antes de la ejecución.

## Estado previo esperado

Antes de usar este anexo, debería haberse cumplido como mínimo lo siguiente:

- la migración fue planificada con backup y rollback documentados
- la fuente de verdad operativa previa de `n8n` fue confirmada
- las dependencias actuales conocidas fueron preservadas o sustituidas de forma controlada
- existe un estado previo conocido contra el cual comparar la operación resultante

Hechos confirmados del estado previo actual:

- `n8n` depende actualmente de `/root/docker-compose.yaml`
- `n8n` depende actualmente de `/root/n8n.env`
- `n8n` depende actualmente de `/root/local-files`
- `n8n` usa actualmente el volumen Docker `root_n8n_data`

## Comprobaciones técnicas mínimas

Tras una futura migración, deberían comprobarse como mínimo los siguientes puntos:

- el servicio `n8n` inicia y permanece estable
- la persistencia de `n8n` resulta accesible e íntegra
- el equivalente funcional del almacenamiento antes asociado a `root_n8n_data` está disponible
- el equivalente funcional del contenido antes disponible en `/root/local-files` sigue accesible
- la configuración cargada por `n8n` es coherente con la esperada para el entorno operativo
- el acceso operativo definido para `n8n` sigue siendo consistente con la arquitectura del VPS

Falta evidencia en este repositorio para definir:

- métricas de rendimiento esperadas
- tiempos máximos aceptables de arranque
- inventario cerrado de artefactos persistentes que deban verificarse uno a uno

## Comprobaciones funcionales mínimas

Como validación funcional mínima, debería confirmarse que:

- los workflows esperados están presentes
- la instancia conserva su configuración operativa esencial
- las funciones dependientes de archivos siguen resolviendo correctamente sus recursos
- las funciones que dependan de persistencia siguen operando sin pérdida evidente de estado

Falta evidencia en este repositorio para definir:

- lista cerrada de workflows críticos
- lista de ejecuciones recientes que deban compararse
- conjunto mínimo de casos funcionales por workflow

## Integraciones que deben verificarse

Deben verificarse, como mínimo, las integraciones críticas realmente usadas por la instancia.

Con la evidencia disponible en este repositorio, no existe una lista confirmada de integraciones activas.
Por tanto, antes de una ejecución futura deberá identificarse explícitamente:

- qué integraciones externas son críticas
- qué integraciones dependen de credenciales o variables sensibles
- qué integraciones dependen de archivos en el mount actualmente asociado a `/root/local-files`
- qué integraciones usan webhooks o puntos de entrada externos

Sin esa identificación, la validación funcional solo puede considerarse parcial.

## Evidencias que deben capturarse

Después de una futura migración, deberían capturarse como mínimo las siguientes evidencias documentales:

- estado del servicio tras el arranque
- confirmación de acceso a persistencia
- confirmación de disponibilidad de archivos necesarios
- evidencia de presencia de workflows esperados
- evidencia de validación de integraciones críticas identificadas
- fecha, alcance y responsable de la validación

No se deben almacenar secretos ni contenidos sensibles en este repositorio.
Si alguna evidencia incluye datos sensibles, deberá referenciarse de forma segura sin copiar su contenido aquí.

## Criterios de éxito

Una futura migración solo debería considerarse exitosa si:

- `n8n` queda operativo y estable
- la persistencia queda disponible y consistente
- el acceso a archivos necesarios se mantiene
- los workflows esperados están presentes
- las integraciones críticas identificadas validan correctamente
- no se detectan síntomas claros de degradación grave o pérdida de estado

## Señales de fallo grave

Deben tratarse como fallo grave, al menos, las siguientes situaciones:

- `n8n` no inicia o no permanece estable
- la persistencia no está disponible o presenta pérdida evidente de estado
- faltan workflows esperados
- los recursos requeridos desde el equivalente de `/root/local-files` no están disponibles
- fallan integraciones críticas identificadas
- el servicio queda accesible de una forma incoherente con el diseño operativo esperado

## Criterios de rollback

Debe considerarse rollback si ocurre cualquiera de estas condiciones:

- no se alcanza un estado operativo estable
- no puede verificarse la integridad mínima de persistencia
- no están disponibles los workflows esperados
- fallan integraciones críticas sin mitigación inmediata aceptable
- no puede demostrarse equivalencia funcional mínima respecto al estado previo esperado

Falta evidencia en este repositorio para fijar:

- umbrales temporales exactos antes de declarar rollback
- orden exacto de restauración
- tiempos objetivo de recuperación

## Checklist breve de validación

- [ ] Servicio `n8n` operativo y estable
- [ ] Persistencia accesible
- [ ] Archivos requeridos accesibles
- [ ] Workflows esperados presentes
- [ ] Integraciones críticas identificadas verificadas
- [ ] Evidencias mínimas capturadas
- [ ] Resultado final clasificado como éxito o rollback

## Referencias

- `runbooks/N8N_MIGRATION_PREP.md`
- `docs/ARCHITECTURE.md`
- `docs/LAYOUT_PHASE_2_PROPOSAL.md`
- `evidence/FASE_1_CIERRE.md`
- `inventory/INITIAL_INVENTORY.md`
