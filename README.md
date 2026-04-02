# DAVLOS Control-Plane

Fuente de verdad operativa del VPS DAVLOS.

## Estado actual

- Fase 1 cerrada.
- Fase 2 cerrada en lo necesario para `n8n`.
- Fase 3 cerrada histórica y operativamente.
- Fase 4 abierta y en pausa operativa.
- La suboperación 4.2 quedó recuperada y no es bloqueo activo.
- Sin secretos en este repositorio.
- OpenClaw ya no está solo en baseline MVP: el boundary opera en host con `inference-gateway`, broker restringido, Telegram persistente y helper readonly.
- La DAVLOS VPN Console ya actúa como CLI operativo del boundary con dashboard, broker/capacidades, seguridad guiada y diagnóstico.

## Objetivo actual

Prioridad operativa vigente:

1. mantener estable el runtime actual de `n8n` y `OpenClaw`
2. consolidar la operación real de consola, broker y Telegram sin abrir superficie innecesaria
3. mantener el helper readonly y el control restringido como baseline seguro del boundary
4. mantener la documentación viva alineada con el estado real ya desplegado y con la operación vigente
5. mantener Fase 4 en pausa hasta nueva decisión operativa

## Estado de n8n

Hechos confirmados en la documentación operativa actual:

- runtime observado: `compose-n8n-1`
- publicación local válida:
  - `127.0.0.1:5678`
  - `127.0.0.1:81`
- topología válida:
  - `verity_network`
  - `root_n8n_data`
- bind mount validado:
  - `/opt/automation/n8n/local-files -> /files`
- `files` usage en el inventario mínimo actual: `skip`
- existe evidencia de recuperación operativa y baseline post-recuperación
- la evidencia reciente confirma topología post-recuperación bajo `/opt` para `local-files`, pero no debe usarse este `README` para afirmar por sí solo que el `compose` activo y el `env` efectivo ya no conservan referencias históricas a `/root`

## Estado de OpenClaw

Checkpoint actual:

- despliegue MVP local ejecutado y validado en host
- broker restringido operativo en host con policy viva y auditoría
- canal Telegram privado operativo como runtime persistente
- helper readonly host-side instalado para inspección segura de broker y Telegram desde consola
- runtime materializado en host bajo:
  - `/opt/automation/agents/openclaw`
  - `/etc/davlos/secrets/openclaw`
- estado validado por evidencia:
  - contenedor `openclaw-gateway` arrancado
  - `inference-gateway` host-side operativo como upstream interno
  - red dedicada `agents_net`
  - endpoint efectivo para OpenClaw: `http://172.22.0.1:11440/v1`
  - health MVP correcto y comprobación TCP válida en `127.0.0.1:18789`
  - imagen desplegada: `ghcr.io/openclaw/openclaw:2026.2.3`
- scripts relevantes:
  - `scripts/agents/openclaw/10_stage_runtime.sh`
  - `scripts/agents/openclaw/20_validate_runtime_readiness.sh`
  - `scripts/agents/openclaw/30_first_local_deploy.sh`
- bootstrap documental:
  - `docs/AGENTS.md`
  - `docs/INFERENCE_GATEWAY_OLLAMA_MVP.md`
  - `docs/AGENT_ZONE_SECURITY_MVP.md`
  - `docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md`
  - `docs/OPENCLAW_SECURITY_BOOTSTRAP_MVP.md`
  - `docs/OPENCLAW_HOST_SECRETS_CONTRACT_MVP.md`
  - `templates/openclaw/openclaw.json.example`
- operación integrada actual en consola:
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh overview`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-capabilities`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-capabilities-audit`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-telegram`
  - `bash /opt/control-plane/scripts/console/davlos-vpn-console.sh openclaw-diagnostics`
- helper readonly host-side para visibilidad runtime:
  - `/usr/local/sbin/davlos-openclaw-readonly`
  - `/etc/sudoers.d/davlos-openclaw-readonly`
- superficie operativa actual:
  - dashboard de consola con estado de host, broker, Telegram y runtime
  - consola reorganizada por runtime, broker, seguridad, evidencias y diagnóstico
  - control guiado de capacidades con TTL y reset one-shot
  - presets de seguridad en consola
  - Telegram como canal corto de consulta, ejecución cerrada y modo conversacional controlado
  - local-first en Telegram: frases conocidas siguen por reglas; el fallback LLM solo entra en `wake` cuando el matcher local no resuelve
  - Gemini puede operar como fallback controlado en runtime mediante env seguro, sin alterar el perímetro `auth/policy/broker`
- límites que siguen vigentes:
  - no hay UI web final de control; la operación principal sigue en consola + Telegram
  - start/stop/restart no se exponen directamente desde la consola
  - el hardening final de egress no se declara cerrado en este README

## Documentos clave

- `docs/ARCHITECTURE.md`
- `docs/AGENTS.md`
- `runbooks/N8N_PRECHECKS_EXECUTION.md`
- `runbooks/N8N_BACKUP_AND_ROLLBACK_MINIMUM.md`
- `runbooks/N8N_MIGRATION_WINDOW_PLAN.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`
- `evidence/agents/OPENCLAW_MVP_VALIDATION_2026-03-31.md`
- `docs/INFERENCE_GATEWAY_OLLAMA_MVP.md`
- `docs/AGENT_ZONE_SECURITY_MVP.md`
- `docs/AGENT_ZONE_EGRESS_ALLOWLIST_MVP.md`
- `runbooks/OPENCLAW_DEPLOY_MVP.md`
- `docs/OPENCLAW_SECURITY_BOOTSTRAP_MVP.md`
- `docs/OPENCLAW_HOST_SECRETS_CONTRACT_MVP.md`
- `docs/CONSOLE_OPENCLAW_CAPABILITIES_MVP.md`
- `docs/DAVLOS_VPN_CONSOLE_PRESENTATION_MVP.md`
- `docs/OPENCLAW_OPERATOR_FLOWS_MVP.md`
- `docs/TELEGRAM_OPENCLAW_RUNTIME_FINAL.md`
- `docs/TELEGRAM_OPENCLAW_CONVERSATIONAL_MVP.md`
- `docs/TELEGRAM_OPENCLAW_LLM_FALLBACK_PHASE_16_17.md`
- `docs/OPENCLAW_READONLY_HELPER_INSTALL.md`

Nota:
Algunos documentos conservan contexto histórico y deben leerse con fecha y alcance. La verdad operativa actual de `n8n` queda reflejada en este `README`, en `evidence/FASE_4_ESTADO.md`, en `evidence/PHASE4_PAUSE_AND_4_2_RECOVERED_2026-03-31.md` y en las evidencias recientes de prechecks. La verdad actual de `OpenClaw` en este checkpoint es: boundary operativo con `inference-gateway`, broker restringido con policy viva y auditoría, Telegram persistente como canal corto, modo conversacional controlado `local-first`, fallback LLM acotado a `wake` y helper readonly host-side para inspección segura desde consola. El hardening final de egress sigue documentado por fases y no se declara cerrado en este `README`.

## Regla base

Este repositorio documenta y prepara cambios.
No debe usarse para introducir secretos ni para asumir que un diseño documental ya equivale a estado operativo real.
