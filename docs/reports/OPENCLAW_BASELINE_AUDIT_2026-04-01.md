# OpenClaw Baseline Audit 2026-04-01

## alcance de la revisión

Revisión local documental y de scripts sobre la rama `codex/openclaw-console-readonly` para dejar un baseline técnico coherente antes de arrancar la ejecución posterior del plan OpenClaw.

Archivos auditados como foco principal:

- `README.md`
- `docs/AGENTS.md`
- `docs/ARCHITECTURE.md`
- `inventory/INITIAL_INVENTORY.md`
- `evidence/agents/OPENCLAW_MVP_VALIDATION_2026-03-31.md`
- `docs/INFERENCE_GATEWAY_OLLAMA_MVP.md`
- `docs/AGENT_ZONE_SECURITY_MVP.md`
- `docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md`
- `runbooks/OPENCLAW_DEPLOY_MVP.md`
- `scripts/console/davlos-vpn-console.sh`
- `scripts/agents/openclaw/30_first_local_deploy.sh`
- `templates/openclaw/docker-compose.yaml`

Fuera de alcance en esta intervención:

- cambios runtime en el VPS
- despliegues reales
- introducción de nuevas capacidades operativas
- broker restringido, Telegram, chat final o acciones A/B/C/D

## rama revisada

- rama local: `codex/openclaw-console-readonly`
- remoto esperado: `origin/codex/openclaw-console-readonly`

## estado actual del proyecto

### n8n

- la evidencia reciente confirma runtime estable `compose-n8n-1`
- siguen validados `127.0.0.1:5678`, `127.0.0.1:81`, `verity_network` y `root_n8n_data`
- el bind mount validado reciente es `/opt/automation/n8n/local-files -> /files`
- sigue existiendo deuda de trazabilidad entre referencias históricas a `/root` y el runtime post-recuperación observado

### OpenClaw

- el MVP local aparece como desplegado y validado, no solo staged
- el runtime materializado vive bajo `/opt/automation/agents/openclaw`
- el contenedor documentado es `openclaw-gateway`
- la red separada es `agents_net`
- el bind host documentado es `127.0.0.1:18789`

### inference-gateway

- el diseño y la evidencia convergen en un gateway host-side mínimo gestionado por `systemd`
- el endpoint efectivo para OpenClaw es `http://172.22.0.1:11440/v1`
- el upstream local documentado sigue siendo Ollama en `127.0.0.1:11434`

## fortalezas

- existe evidencia reciente y concreta del MVP local de OpenClaw
- la separación de zona de agentes está bien planteada a nivel de red, mounts y principio de mínimo privilegio
- la consola readonly ya ofrece observabilidad útil de `OpenClaw` e `inference-gateway`
- el repositorio mantiene la disciplina de no incluir secretos reales
- el enfoque general del control-plane sigue siendo conservador y reversible

## contradicciones detectadas

### críticas

- `README.md` describía OpenClaw como staged y no desplegado, pero la evidencia `evidence/agents/OPENCLAW_MVP_VALIDATION_2026-03-31.md` lo deja como desplegado, con contenedor, red y gateway operativos

### altas

- `docs/AGENTS.md` seguía como placeholder genérico y no reflejaba ni el runtime real de OpenClaw ni la consola readonly ya existente
- `docs/ARCHITECTURE.md` seguía describiendo `n8n` solo desde `/root` y no recogía el estado observado reciente bajo `/opt` ni la existencia operativa de `OpenClaw` e `inference-gateway`
- `README.md` afirmaba como verdad operativa cerrada que `n8n` opera desde `/opt/automation/n8n/compose` y `/opt/automation/n8n/env`, pero la evidencia reciente soporta con claridad el bind mount bajo `/opt` y el runtime actual, no necesariamente toda la trazabilidad final de `compose` y `env`

### medias

- `inventory/INITIAL_INVENTORY.md` queda claramente como snapshot histórico de Fase 1 y ya no debe leerse como fotografía actual completa del host
- el runbook `runbooks/OPENCLAW_DEPLOY_MVP.md` pedía `docker inspect` bruto, que es útil operativamente pero arriesga exponer variables sensibles del contenedor

## riesgos inmediatos

### críticos

- `scripts/agents/openclaw/30_first_local_deploy.sh` imprimía `docker inspect` bruto y lanzaba una comprobación con token en línea de comandos; ambas salidas podían exponer `OPENCLAW_GATEWAY_TOKEN` o material sensible derivado del runtime

### altos

- el mismo script dejaba `/etc/davlos/secrets` y `/etc/davlos/secrets/openclaw` con permisos `0755`, demasiado abiertos para un path diseñado para secretos futuros
- la consola readonly mostraba logs y `journalctl` sin redacción, con riesgo de arrastrar tokens, `apiKey`, cabeceras o payloads a la salida de operador
- la allowlist real de egress sigue sin estar aplicada en runtime, así que la postura de red sigue siendo MVP documental, no enforcement real

### medios

- la versión de imagen sigue fijada por tag y no por digest
- el hardening del healthcheck sigue siendo suficiente para MVP, pero no necesariamente para una siguiente fase con más superficie
- persiste deuda en la alineación del helper readonly legado de `n8n` respecto al runtime actual

## deuda técnica abierta

- decidir pin final de imagen para OpenClaw, idealmente por digest
- definir si `OPENCLAW_GATEWAY_TOKEN` debe migrar desde `.env` a `/etc/davlos/secrets/openclaw`
- aplicar allowlist real de egress para `agents_net`
- validar funcionalmente el runtime OpenClaw ya desplegado sin reabrir diseño de red
- consolidar trazabilidad final de `compose` y `env` de `n8n`
- decidir cómo versionar la diferencia entre inventarios históricos y estado operativo vigente

## cambios aplicados en esta intervención

### documentación

- `README.md`
  - alineado con la evidencia real reciente de OpenClaw
  - rebajada la afirmación excesiva sobre `n8n` para no inventar estado no soportado
  - mejorado el listado de documentos clave del baseline OpenClaw
- `docs/AGENTS.md`
  - reemplazado placeholder por baseline operativo realista y trazable
  - explicitado qué existe hoy y qué todavía no debe darse por implementado
- `docs/ARCHITECTURE.md`
  - alineado con la evidencia reciente de `n8n`
  - añadidos `OpenClaw` e `inference-gateway` como parte real de la arquitectura actual
- `runbooks/OPENCLAW_DEPLOY_MVP.md`
  - sustituidas validaciones inseguras por inspecciones formateadas
  - añadida nota explícita para no imprimir `.env` ni usar `docker inspect` bruto salvo necesidad justificada

### scripts

- `scripts/agents/openclaw/30_first_local_deploy.sh`
  - permisos endurecidos para `/etc/davlos/secrets` y `/etc/davlos/secrets/openclaw` a `0750`
  - redacción mínima de salida sensible en logs de error y post-checks
  - eliminación de `docker inspect` bruto en post-checks
  - retirada de la comprobación que pasaba token por línea de comandos
- `scripts/console/davlos-vpn-console.sh`
  - redacción mínima de salida sensible en logs Docker, logs locales y `journalctl`

## backlog priorizado para arrancar el plan OpenClaw

### P0

- validar desde una sesión autorizada que el runtime desplegado sigue sano tras el baseline documental
- capturar evidencia saneada de `OpenClaw` e `inference-gateway` ya con el flujo de logs/redacción actualizado
- cerrar una decisión explícita sobre si el token local del gateway sigue en `.env` o pasa a secreto host-side

### P1

- aplicar allowlist real de egress para `agents_net`
- fijar imagen por digest o dejar criterio de actualización documentado y controlado
- decidir el nivel final de healthcheck y observabilidad que se exige para la siguiente fase

### P2

- consolidar documentación histórica vs actual de `n8n` para que `README`, arquitectura e inventarios no mezclen snapshots de fases distintas
- revisar si el template `templates/openclaw/docker-compose.yaml` necesita una nota adicional de contrato sobre logs y secretos

### P3

- diseñar después el broker restringido, Telegram, chat final y acciones A/B/C/D sobre una base ya endurecida

## validación ejecutada en esta intervención

- revisión manual del diff aplicado
- `bash -n scripts/agents/openclaw/30_first_local_deploy.sh`
- `bash -n scripts/console/davlos-vpn-console.sh`

No ejecutado por seguridad y alcance:

- `docker compose up`
- `docker inspect` contra runtime real
- llamadas `curl` contra servicios del VPS
- cambios `systemd`

## ficheros no corregidos todavía de forma deliberada

- `inventory/INITIAL_INVENTORY.md`
  - se conserva como inventario inicial histórico
- artefactos no versionados presentes en el árbol:
  - `evidence/prechecks/n8n/2026-03-31/45_n8n_workflow_inventory_readonly.txt`
  - `scripts/prechecks/n8n/45_n8n_workflow_inventory_readonly.sh`
  - `templates/inference-gateway/`
  - no se tocaron en esta intervención por no ser requisito directo del baseline OpenClaw

## recomendación clara de siguiente paso

Congelar esta rama como baseline documental y de seguridad mínima, publicar el commit en `codex/openclaw-console-readonly` y arrancar después una Fase 0 corta de validación controlada del runtime ya desplegado.

Esa siguiente fase debería limitarse a:

- comprobar salud y logs saneados del runtime real
- decidir ubicación final del token local del gateway
- aplicar allowlist real de egress antes de introducir cualquier control activo o integración adicional
