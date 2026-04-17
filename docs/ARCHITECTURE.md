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
  - runtime observado: `compose-n8n-1`
  - bind mount confirmado: `/opt/automation/n8n/local-files -> /files`
  - publicación local validada: `127.0.0.1:5678`
  - red validada: `verity_network`
  - volumen Docker `root_n8n_data`
- OpenClaw (bot Telegram Python — **sin Docker desde Phase 7**):
  - policy y audit: `/opt/automation/agents/openclaw/broker/`
  - secretos: `/etc/davlos/secrets/openclaw`
  - servicio: `openclaw-telegram-bot.service`
  - vault LLM local: `qwen2.5:3b` vía Ollama en `http://127.0.0.1:11440/v1`
- inference-gateway / Ollama:
  - `/opt/automation/inference-gateway`
  - unidad `systemd` `inference-gateway.service`
  - endpoint local `http://127.0.0.1:11440/v1/chat/completions`

Conclusión de arquitectura actual:

- La producción y el staging de Verity todavía residen en un layout heredado bajo `/opt/verity-stack`.
- La infraestructura PostgreSQL ya está fuera de `/root`, pero no bajo la zona objetivo `/opt/infra`.
- `n8n` ya muestra topología post-recuperación parcialmente alineada con `/opt`, pero la evidencia readonly reciente no debe usarse para afirmar que toda la definición activa haya dejado atrás referencias históricas a `/root`.
- `OpenClaw` e `inference-gateway` ya materializan parte de la zona objetivo de automatización separada.
- La arquitectura objetivo queda definida, pero no debe confundirse con un cierre completo del hardening ni de la transición documental.

## Mapeo formal actual -> objetivo

- `/opt/verity-stack/verity-news` -> `/opt/apps/prod/verity-news`
- `/opt/verity-stack/staging/verity-news-staging` -> `/opt/apps/staging/verity-news`
- `/opt/verity-stack/npm` -> `/opt/infra/npm`
- `/opt/verity-postgres` -> `/opt/infra/postgres`
- `compose-n8n-1` + `verity_network` + `root_n8n_data` -> runtime validado de `n8n` pendiente de trazabilidad completa sobre `compose` y `env`
- `/opt/automation/n8n/local-files` -> bind mount operativo confirmado de `n8n`
- volumen Docker `root_n8n_data` -> persistencia futura a definir para `/opt/automation/n8n`
- `/opt/automation/agents/openclaw` -> runtime operativo de `OpenClaw` (policy + audit; bot directo en host vía systemd)
- `/opt/automation/inference-gateway` -> boundary host-side para inferencia local
- `/etc/davlos/secrets/openclaw` -> contrato host-side de secretos para agentes

Notas:

- El estado de `n8n` debe leerse como mixto: hay evidencias válidas de runtime y de bind mount bajo `/opt`, pero no debe darse por cerrada la trazabilidad final de `compose` y `env` solo con este documento.
- `OpenClaw` e `inference-gateway` sí tienen evidencia operativa reciente en esta rama, pero su baseline sigue siendo MVP y no hardening final.
- No hay evidencia confirmada en esta fase sobre WireGuard ni sobre cargas reales para `/opt/apps/lab`.

## Reglas de transición para fases posteriores

- No mezclar rediseño documental y migración operativa en un solo cambio.
- Validar primero dependencias reales, redes, volúmenes, secretos y rollback por servicio.
- Mantener la evidencia histórica intacta.
- Documentar antes de mover.
- Ejecutar cualquier migración futura por servicio, no por lote global.

## Bloqueos conocidos

- `n8n` mantiene deuda de trazabilidad entre referencias históricas a `/root` y runtime observado reciente bajo `/opt`.
- No se debe inferir que una ruta objetivo exista ya solo porque esté definida documentalmente.
- La allowlist real de egress para `agents_net` todavía no está aplicada.
- No hay validación en este documento de backups restaurables por servicio ni de pruebas funcionales completas de OpenClaw.

Referencia operativa asociada:

- Preparación documental de `n8n`: `runbooks/N8N_MIGRATION_PREP.md`

## Alcance de este documento

Este documento fija la arquitectura objetivo deseada y su relación con el estado actual confirmado.
La ejecución de cambios operativos queda fuera de este alcance.
