# Arquitectura objetivo DAVLOS

## Propósito

Este documento define la arquitectura documental objetivo del VPS DAVLOS para la siguiente fase de ordenación operativa.

No describe una migración ejecutada.
No sustituye el inventario histórico de Fase 1.
No autoriza movimientos de servicios, secretos ni cambios en producción.

## Principios de diseño

- Separación clara por zonas operativas.
- Fuente de verdad documental centralizada en `/opt/control-plane`.
- Servicios de producción, staging, automatización e infraestructura aislados por dominio funcional.
- Cambios reversibles y por etapas pequeñas.
- Ninguna reubicación debe ejecutarse sin validación previa de dependencias, backup y rollback.

## Layout objetivo por zonas

### Aplicaciones

- `/opt/apps/prod`
  - Servicios de aplicación en producción.
- `/opt/apps/staging`
  - Servicios de aplicación de preproducción y validación.
- `/opt/apps/lab`
  - Espacio reservado para pruebas controladas o stacks temporales no críticos.

### Automatización

- `/opt/automation/n8n`
  - Ubicación objetivo deseada para la operación futura de `n8n`.
- `/opt/automation/agents`
  - Ubicación objetivo para agentes, workers o automatizaciones auxiliares.
- `/opt/automation/policies`
  - Políticas operativas, reglas y documentos de control aplicables a automatización.

### Infraestructura

- `/opt/infra/npm`
  - Infraestructura de publicación y proxy inverso basada en Nginx Proxy Manager.
- `/opt/infra/postgres`
  - Infraestructura de base de datos PostgreSQL compartida o dedicada.
- `/opt/infra/wireguard`
  - Ubicación objetivo reservada para WireGuard cuando su realidad operativa sea documentada.

### Gobierno documental y respaldo

- `/opt/control-plane`
  - Fuente de verdad documental, runbooks, políticas, evidencia e inventarios.
- `/opt/backups`
  - Zona objetivo para respaldos gestionados y trazables.

## Estado real confirmado frente al layout objetivo

Rutas operativas confirmadas actualmente:

- Verity prod:
  - `WORKDIR=/opt/verity-stack/verity-news`
  - `CONFIG=/opt/verity-stack/verity-news/compose.yml`
- Verity staging:
  - `/opt/verity-stack/staging/verity-news-staging/docker-compose.yml`
- NPM:
  - `/opt/verity-stack/npm/docker-compose.yml`
- Postgres prod:
  - `/opt/verity-postgres/docker-compose.yml`
- n8n:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`

Conclusión de arquitectura actual:

- La producción y el staging de Verity todavía residen en un layout heredado bajo `/opt/verity-stack`.
- La infraestructura PostgreSQL ya está fuera de `/root`, pero no bajo la zona objetivo `/opt/infra`.
- `n8n` sigue fuera del layout objetivo y mantiene dependencia operativa explícita de `/root`.
- La arquitectura objetivo queda definida, pero aún no está materializada en producción.

## Mapeo formal actual -> objetivo

- `/opt/verity-stack/verity-news` -> `/opt/apps/prod/verity-news`
- `/opt/verity-stack/staging/verity-news-staging` -> `/opt/apps/staging/verity-news`
- `/opt/verity-stack/npm` -> `/opt/infra/npm`
- `/opt/verity-postgres` -> `/opt/infra/postgres`
- `/root/docker-compose.yaml` -> probable futuro dominio documental de `/opt/automation/n8n`
- `/root/n8n.env` -> probable futuro dominio operativo de `/opt/automation/n8n`
- `/root/local-files` -> probable futuro dominio operativo de `/opt/automation/n8n`
- volumen Docker `root_n8n_data` -> persistencia futura a definir para `/opt/automation/n8n`

Notas:

- El mapeo de `n8n` es objetivo de diseño, no estado ejecutado.
- No hay evidencia confirmada en esta fase sobre WireGuard ni sobre cargas reales para `/opt/apps/lab`, `/opt/automation/agents` y `/opt/automation/policies`.

## Reglas de transición para fases posteriores

- No mezclar rediseño documental y migración operativa en un solo cambio.
- Validar primero dependencias reales, redes, volúmenes, secretos y rollback por servicio.
- Mantener la evidencia histórica intacta.
- Documentar antes de mover.
- Ejecutar cualquier migración futura por servicio, no por lote global.

## Bloqueos conocidos

- `n8n` depende de rutas activas bajo `/root`, por lo que no debe considerarse alineado al layout objetivo.
- No se debe inferir que una ruta objetivo exista ya solo porque esté definida documentalmente.
- No hay validación en este documento de backups restaurables por servicio.

Referencia operativa asociada:

- Preparación documental de `n8n`: `runbooks/N8N_MIGRATION_PREP.md`

## Alcance de este documento

Este documento fija la arquitectura objetivo deseada y su relación con el estado actual confirmado.
La ejecución de cambios operativos queda fuera de este alcance.
