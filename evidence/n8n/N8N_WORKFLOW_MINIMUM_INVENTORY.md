# N8N Workflow Minimum Inventory

## 1. objetivo

Dejar una base mínima y readonly sobre workflows reales de `n8n` para reanudar Fase 4 con trazabilidad funcional sin exponer secretos ni tocar producción.

## 2. estado actual conocido

- `n8n` sigue operativo en la topología validada reciente
- el helper `45_n8n_workflow_inventory_readonly.sh` quedó creado y es válido sintácticamente
- la ejecución readonly de ese helper en esta sesión no pudo listar workflows porque no hubo acceso efectivo a Docker desde la sesión de trabajo actual
- el wrapper readonly NOPASSWD disponible en host sigue apuntando a un contenedor legado (`root-n8n-1`) para parte del inventario y no sirve hoy como fuente final del runtime funcional activo

## 3. inventario mínimo observado

- `clawbot_staging_receiver`
  - estado de confirmación: parcial
  - fuente: evidencia documental existente en `docs/examples/N8N_WORKFLOW_INVENTORY_REAL_PARTIAL_01.md`
- listado directo por CLI de workflows de la instancia activa: no concluyente
  - fuente: `evidence/prechecks/n8n/2026-03-31/45_n8n_workflow_inventory_readonly.txt`
- runtime activo validado por otras evidencias recientes:
  - `compose-n8n-1`
  - `127.0.0.1:5678`
  - `verity_network`
  - bind mount `/opt/automation/n8n/local-files:/files`

## 4. clasificación mínima por trigger (webhook / cron / manual / desconocido)

- `clawbot_staging_receiver`: `webhook`
- resto de workflows reales de la instancia activa: `desconocido`

## 5. dependencia de archivos local-files (sí / no / no concluyente)

- `clawbot_staging_receiver`: `no concluyente`
- instancia `n8n` con bind mount disponible en `/files`: confirmado en evidencia reciente

## 6. criticidad inicial (crítico / importante / laboratorio / no concluyente)

- `clawbot_staging_receiver`: `laboratorio`
  - motivo: asociado documentalmente a Clawbot en staging
- resto de workflows reales de la instancia activa: `no concluyente`

## 7. huecos pendientes

- reejecutar el helper `45` desde una sesión con acceso efectivo a Docker
- sustituir o alinear el wrapper readonly legado del host para que no siga mirando `root-n8n-1`
- confirmar listado real de workflows activos/inactivos
- confirmar ID no sensible del workflow `clawbot_staging_receiver`
- confirmar si `clawbot_staging_receiver` usa o no `/files`
- confirmar si existen workflows `cron` o `manual` en la instancia activa

## 8. siguiente paso recomendado

Mantener Fase 4 como `PARTIAL` en su inventario funcional mínimo, usar como baseline la evidencia operativa ya validada del runtime actual y repetir `scripts/prechecks/n8n/45_n8n_workflow_inventory_readonly.sh` desde una sesión con acceso readonly real a Docker antes de dar por cerrado el inventario de workflows.
