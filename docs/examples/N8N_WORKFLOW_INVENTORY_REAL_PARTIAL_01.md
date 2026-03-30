# Ficha real parcial de inventario de workflow de n8n 01

## Nota inicial

Esta es una primera ficha real parcial.
No debe usarse todavía para decisiones de migración.
Su objetivo es validar el flujo documental con un caso real no sensible y comprobar que la estructura de captura resulta utilizable con evidencia limitada.

## Propósito

Esta ficha documenta de forma parcial un workflow real de `n8n` usando únicamente evidencia no sensible disponible en el control-plane.

En esta fase solo se capturan:

- identificación del workflow
- propósito breve
- trigger principal
- integración principal
- uso de archivos
- criticidad estimada
- validación mínima esperada
- evidencias pendientes

Todo dato no confirmado queda marcado explícitamente como `pendiente de evidenciar`.

## Estado de inventario

- Estado actual: `parcial`
- Fecha de captura: `2026-03-30`
- Última revisión: `2026-03-30`
- Responsable documental: `pendiente de evidenciar`

## Identificación del workflow

- Nombre visible del workflow:
  - `clawbot_staging_receiver`
- ID interno de `n8n`:
  - `pendiente de evidenciar`
- Estado observado:
  - `parcialmente confirmado`
- Clasificación de uso:
  - `workflow sencillo y no crítico, pendiente de evidenciar`
- Propósito breve:
  - workflow real de la instancia `n8n` identificado nominalmente como `clawbot_staging_receiver`
  - por el nombre visible, actúa previsiblemente como receptor asociado a staging, pero el propósito funcional exacto queda pendiente de evidenciar
- Fuente de evidencia utilizada:
  - `inventory/INITIAL_INVENTORY.md`
  - `evidence/FASE_1_CIERRE.md`
  - `docs/N8N_FUNCTIONAL_DEPENDENCIES.md`

## Criticidad

- Criticidad estimada: `baja`
- Estado de confirmación:
  - `estimación provisional`
- Justificación de la estimación:
  - esta ficha se reserva para un caso sencillo y no crítico
  - no existe todavía evidencia suficiente en el repositorio para clasificar impacto real por nombre de workflow
- Impacto si falla:
  - `pendiente de evidenciar`
- Requiere rollback inmediato si falla:
  - `pendiente de evidenciar`

## Trigger principal

- Tipo de trigger principal:
  - `webhook`
- Patrón general de activación:
  - `pendiente de evidenciar`
- Frecuencia esperada:
  - `pendiente de evidenciar`
- Observación documental:
  - el tipo de trigger principal queda confirmado como `webhook`
  - endpoint exacto, patrón de llamada y frecuencia permanecen pendientes de evidenciar

## Integración principal

- Integración principal:
  - `pendiente de evidenciar`
- Sistema o emisor invocador:
  - `pendiente de evidenciar`
- Tipo de integración:
  - `webhook entrante, pendiente de evidenciar con mayor precisión`
- Dirección del flujo:
  - `entrante, pendiente de evidenciar`
- Estado de confirmación:
  - `parcial`
- Observación documental:
  - el nombre del workflow y el trigger `webhook` sugieren una recepción desde un sistema externo en staging
  - el sistema o emisor invocador concreto no quedó aportado con un valor confirmable en esta actualización
  - no existe todavía evidencia suficiente en el repositorio para nombrar con precisión la integración principal sin inferencia adicional
  - `docs/N8N_FUNCTIONAL_DEPENDENCIES.md` indica que no existe todavía una lista confirmada de integraciones activas por workflow

## Uso de archivos y `local-files`

- ¿El workflow depende de archivos locales?:
  - `pendiente`
- Referencia documental disponible:
  - la instancia `n8n` tiene documentado un bind mount `/root/local-files -> /files`
- Aplicación concreta a este workflow:
  - `pendiente de evidenciar`
- Observación:
  - no debe inferirse uso real de archivos por este workflow hasta contar con evidencia específica

## Validación mínima esperada

- Validación mínima esperada:
  - confirmar que el workflow `clawbot_staging_receiver` existe y puede identificarse sin exponer datos sensibles
  - confirmar su trigger principal `webhook`
  - confirmar su integración principal
  - confirmar si usa o no archivos locales
- Indicador mínimo de avance documental:
  - la ficha puede pasar de `parcial` a un parcial más sólido cuando identificación, trigger e integración principal queden sustentados con evidencia no sensible
- Resultado funcional esperado:
  - `pendiente de evidenciar`

## Evidencias pendientes

- [x] Nombre visible del workflow confirmado
- [ ] ID interno no sensible o referencia estable confirmada
- [x] Trigger principal confirmado
- [ ] Integración principal confirmada
- [ ] Sistema o emisor invocador confirmado
- [ ] Uso de archivos locales confirmado como `sí`, `no` o `pendiente documentado`
- [ ] Validación funcional mínima específica descrita
- [ ] Responsable documental identificado

## Referencias cruzadas mínimas

- `templates/N8N_WORKFLOW_AND_INTEGRATION_INVENTORY_TEMPLATE.md`
- `docs/N8N_INVENTORY_CAPTURE_GUIDE.md`
- `docs/N8N_FUNCTIONAL_DEPENDENCIES.md`
- `runbooks/N8N_MIGRATION_PREP.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`

## Resumen final

- Clasificación final del inventario:
  - `parcial`
- Motivo del estado final:
  - existe evidencia real de la instancia `n8n` y de su contexto operativo general
  - el workflow queda identificado nominalmente como `clawbot_staging_receiver`
  - el trigger principal `webhook` queda confirmado
  - sistema invocador, integración principal exacta, uso de archivos e identificación técnica estable siguen `pendiente de evidenciar`
- Próxima acción documental recomendada:
  - completar primero el sistema o emisor invocador exacto y confirmar si el workflow usa o no archivos locales, sin exponer datos sensibles
