# Dependencias funcionales conocidas de n8n

## Objetivo

Documentar las dependencias funcionales conocidas y las dependencias funcionales aún no confirmadas de `n8n` para reducir riesgo antes de una futura migración operativa.

Este documento no ejecuta cambios.
Este documento no autoriza una migración.
Este documento no contiene secretos ni valores sensibles.

## Estado actual confirmado

Hechos confirmados actualmente:

- `n8n` sigue dependiendo operativamente de `/root`
- la definición operativa actual está asociada a `/root/docker-compose.yaml`
- las variables de entorno actuales están asociadas a `/root/n8n.env`
- existe un bind mount activo asociado a `/root/local-files`
- la persistencia actual está asociada al volumen Docker `root_n8n_data`
- el objetivo futuro deseado es llevar `n8n` a `/opt/automation/n8n`

Este documento parte de esos hechos y no asume más alcance del que ya está confirmado en el control-plane.

## Dependencias técnicas confirmadas

Dependencias técnicas confirmadas con evidencia previa:

- `/root/docker-compose.yaml`
- `/root/n8n.env`
- `/root/local-files`
- volumen Docker `root_n8n_data`

Dependencias técnicas probables pero no confirmadas en este documento:

- red o redes específicas asociadas a la instancia
- labels, restart policy u otros parámetros adicionales definidos en compose
- dependencias indirectas derivadas del contenido real de variables de entorno

Si esas dependencias son relevantes para ejecución futura, deberán documentarse con evidencia específica antes de mover nada.

## Dependencias funcionales conocidas

Con la evidencia disponible en este repositorio, las dependencias funcionales conocidas pueden afirmarse solo a nivel general:

- `n8n` depende de persistencia operativa
- `n8n` depende de configuración de entorno
- `n8n` depende de acceso a archivos montados
- `n8n` depende de workflows e integraciones cuya continuidad deberá preservarse

Estas dependencias son funcionalmente relevantes porque ya existen evidencias de:

- un volumen persistente en uso
- un archivo de entorno en uso
- un bind mount en uso

No existe en este repositorio una lista confirmada de workflows, credenciales, integraciones o entradas externas concretas.

## Dependencias funcionales no confirmadas

Faltan por confirmar, al menos, las siguientes dependencias funcionales:

- qué workflows están activos
- qué workflows son críticos para operación
- qué integraciones externas usa realmente la instancia
- qué automatizaciones dependen de archivos ubicados en `/root/local-files`
- qué automatizaciones dependen de webhooks o endpoints externos
- qué dependencias funcionales derivan del contenido real de `/root/n8n.env`
- si existen tareas programadas, colas o ejecuciones que requieran validación específica

Mientras esas dependencias no estén inventariadas, cualquier planificación de migración debe considerarse incompleta.

## Uso potencial de /root/local-files

Hecho confirmado:

- `/root/local-files` está asociado operativamente a `n8n`

Interpretación prudente:

- es razonable tratar `/root/local-files` como dependencia funcional potencial hasta demostrar lo contrario

Usos potenciales que deben inventariarse antes de una migración:

- archivos de entrada consumidos por workflows
- archivos intermedios o temporales usados por automatizaciones
- archivos de salida generados por workflows
- dependencias locales referenciadas por nodos o scripts auxiliares

No hay evidencia confirmada en este repositorio para afirmar cuál de esos usos aplica realmente hoy.

## Integraciones externas a inventariar

Con la evidencia actual, no existe una lista confirmada de integraciones externas activas.

Antes de cualquier migración futura, deberá inventariarse al menos:

- integraciones API salientes
- integraciones API entrantes o webhooks
- integraciones con correo, mensajería o notificaciones
- integraciones con almacenamiento o intercambio de archivos
- integraciones con bases de datos o servicios internos
- integraciones que dependan de credenciales gestionadas fuera de este repositorio

No deben registrarse secretos ni valores sensibles en esta ficha.

## Workflows o categorías de workflows a inventariar

Con la evidencia actual, no existe una lista confirmada de workflows concretos.

Antes de una migración futura, debería clasificarse al menos:

- workflows críticos para operación
- workflows programados
- workflows disparados por webhook
- workflows dependientes de archivos
- workflows dependientes de persistencia histórica
- workflows de prueba, laboratorio o uso no crítico

Sin esta clasificación, la validación posterior solo podrá ser parcial.

## Criticidad operativa a clasificar

La criticidad operativa de `n8n` todavía no está clasificada formalmente en este repositorio.

Como mínimo, deberá clasificarse:

- workflows críticos cuya caída exige rollback
- workflows importantes pero recuperables
- workflows no críticos o de laboratorio
- integraciones cuya pérdida afecta continuidad operativa
- dependencias de archivos cuya ausencia bloquea ejecución

No hay evidencia suficiente para asignar hoy esa criticidad por flujo o integración.

## Evidencias que faltan

Falta evidencia documental sobre:

- inventario de workflows activos
- inventario de integraciones activas
- criticidad por workflow
- criticidad por integración
- uso real del contenido de `/root/local-files`
- dependencias funcionales derivadas de `/root/n8n.env`
- criterios funcionales concretos para comparar estado previo y posterior

Sin esa evidencia, la preparación de migración solo puede considerarse parcial.

## Checklist de información pendiente

- [ ] Inventario de workflows activos
- [ ] Clasificación de workflows críticos
- [ ] Inventario de integraciones externas activas
- [ ] Identificación de workflows dependientes de archivos
- [ ] Identificación del uso real de `/root/local-files`
- [ ] Identificación de entradas por webhook
- [ ] Identificación de dependencias derivadas del entorno
- [ ] Clasificación de criticidad operativa
- [ ] Definición de validaciones funcionales mínimas por categoría

## Referencias

- `runbooks/N8N_MIGRATION_PREP.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`
- `docs/ARCHITECTURE.md`
- `docs/LAYOUT_PHASE_2_PROPOSAL.md`
- `evidence/FASE_1_CIERRE.md`
- `inventory/INITIAL_INVENTORY.md`
