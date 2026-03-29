# Propuesta de layout Fase 2

## Resumen

Fase 2 debe formalizar el layout objetivo por zonas sin mover todavía servicios críticos ni reubicar datos operativos.

El objetivo inmediato de esta propuesta es dejar un mapa claro entre la realidad actual confirmada y la estructura deseada, para que futuras acciones se ejecuten por servicio, con validación previa y sin mezclar documentación con migraciones.

## Rutas actuales confirmadas

### Producción

- Verity prod
  - `WORKDIR=/opt/verity-stack/verity-news`
  - `CONFIG=/opt/verity-stack/verity-news/compose.yml`
- PostgreSQL prod
  - `/opt/verity-postgres/docker-compose.yml`
- Nginx Proxy Manager
  - `/opt/verity-stack/npm/docker-compose.yml`

### Staging

- Verity staging
  - `/opt/verity-stack/staging/verity-news-staging/docker-compose.yml`

### Automatización

- n8n
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`

## Rutas objetivo por zona

### Apps

- `/opt/apps/prod`
- `/opt/apps/staging`
- `/opt/apps/lab`

### Automation

- `/opt/automation/n8n`
- `/opt/automation/agents`
- `/opt/automation/policies`

### Infra

- `/opt/infra/npm`
- `/opt/infra/postgres`
- `/opt/infra/wireguard`

### Gobierno y backup

- `/opt/control-plane`
- `/opt/backups`

## Mapeo actual -> objetivo

| Actual | Objetivo | Estado |
|---|---|---|
| `/opt/verity-stack/verity-news` | `/opt/apps/prod/verity-news` | Confirmado como mapeo objetivo |
| `/opt/verity-stack/staging/verity-news-staging` | `/opt/apps/staging/verity-news` | Confirmado como mapeo objetivo |
| `/opt/verity-stack/npm` | `/opt/infra/npm` | Confirmado como mapeo objetivo |
| `/opt/verity-postgres` | `/opt/infra/postgres` | Confirmado como mapeo objetivo |
| `/root/docker-compose.yaml` | `/opt/automation/n8n` | Objetivo deseado, no ejecutado |
| `/root/n8n.env` | `/opt/automation/n8n` | Objetivo deseado, no ejecutado |
| `/root/local-files` | `/opt/automation/n8n` | Objetivo deseado, no ejecutado |
| volumen `root_n8n_data` | persistencia asociada a `/opt/automation/n8n` | Objetivo probable, no definido todavía |

## Dependencias y bloqueos

### Dependencias confirmadas

- Verity prod depende de `compose.yml` en `/opt/verity-stack/verity-news`.
- Verity staging depende de su compose en `/opt/verity-stack/staging/verity-news-staging`.
- NPM depende de su compose en `/opt/verity-stack/npm`.
- PostgreSQL prod depende de su compose en `/opt/verity-postgres`.
- `n8n` depende operativamente de:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`

### Bloqueos

- `n8n` no está desacoplado de `/root`.
- No se debe asumir aún una estrategia confirmada de persistencia final para `n8n`.
- No hay evidencia nueva en esta tarea sobre WireGuard; la ruta `/opt/infra/wireguard` queda reservada como objetivo de diseño.
- No hay evidencia nueva en esta tarea sobre servicios reales para `/opt/apps/lab`, `/opt/automation/agents` o `/opt/automation/policies`; esas rutas quedan definidas solo como estructura objetivo.

## Qué no debe moverse todavía

- `n8n`, incluyendo:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`
- Verity prod en `/opt/verity-stack/verity-news`
- Verity staging en `/opt/verity-stack/staging/verity-news-staging`
- NPM en `/opt/verity-stack/npm`
- PostgreSQL prod en `/opt/verity-postgres`

## Criterio operativo para la siguiente fase

La siguiente fase debería centrarse en preparar documentación de transición por servicio, empezando por el caso con mayor deuda estructural: `n8n`.

Eso implica documentar:

- precondiciones
- dependencias reales
- backup y rollback
- orden de validación

Sin ejecutar aún cambios de ruta ni migraciones.

Referencia asociada:

- Runbook de preparación de `n8n`: `runbooks/N8N_MIGRATION_PREP.md`
