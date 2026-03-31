# DAVLOS Control-Plane

Fuente de verdad operativa del VPS DAVLOS.

## Estado actual

- Fase 1 cerrada.
- Fase 2 cerrada en lo necesario para `n8n`.
- Fase 3 cerrada histórica y operativamente.
- Fase 4 abierta y en pausa operativa.
- La suboperación 4.2 quedó recuperada y no es bloqueo activo.
- Sin secretos en este repositorio.
- Sin cambios de producción ejecutados desde este repositorio.

## Objetivo actual

Prioridad operativa vigente:

1. mantener el estado estable actual de `n8n`
2. consolidar trazabilidad mínima de Fase 4
3. revalidar tooling readonly antes de cualquier siguiente cambio
4. mantener Fase 4 en pausa hasta nueva decisión operativa

## Estado de n8n

Hechos confirmados en la documentación operativa actual:

- `n8n` opera desde:
  - `/opt/automation/n8n/compose/docker-compose.yaml`
  - `/opt/automation/n8n/env/n8n.env`
  - `/opt/automation/n8n/local-files`
- runtime observado: `compose-n8n-1`
- publicación local válida:
  - `127.0.0.1:5678`
  - `127.0.0.1:81`
- topología válida:
  - `verity_network`
  - `root_n8n_data`
- `files` usage: `skip`
- existe evidencia de recuperación operativa y baseline post-recuperación

## Documentos clave

- `docs/ARCHITECTURE.md`
- `docs/LAYOUT_PHASE_2_PROPOSAL.md`
- `runbooks/N8N_PRECHECKS_EXECUTION.md`
- `runbooks/N8N_BACKUP_AND_ROLLBACK_MINIMUM.md`
- `runbooks/N8N_MIGRATION_WINDOW_PLAN.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`

## Regla base

Este repositorio documenta y prepara cambios.
No debe usarse para introducir secretos ni para asumir que un diseño documental ya equivale a estado operativo real.
