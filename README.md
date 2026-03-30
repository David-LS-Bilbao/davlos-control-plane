# DAVLOS Control-Plane

Fuente de verdad operativa del VPS DAVLOS.

## Estado actual

- Fase 1 cerrada.
- Fase 2 documental y operativa en preparación.
- Sin secretos en este repositorio.
- Sin cambios de producción ejecutados desde este repositorio.

## Objetivo actual

Prioridad operativa vigente:

1. cerrar el inventario mínimo útil de `n8n`
2. preparar y validar prechecks técnicos reales
3. preparar la futura migración de `n8n` fuera de `/root`
4. continuar la materialización del layout final del VPS por fases

## Estado de n8n

Hechos confirmados en la documentación operativa actual:

- `n8n` sigue dependiendo de:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`
  - red Docker `verity_network`
- `n8n` está en `127.0.0.1:5678` detrás de NPM
- existe pack de prechecks y runbooks operativos para preparar la futura intervención
- todavía no debe ejecutarse la migración sin ventana aprobada, backup verificado y rollback listo

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
