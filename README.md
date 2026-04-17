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

Checkpoint actual (2026-04-17) — **Fases 1-9 completas, rama `feat/phase8-vault-crud` pendiente de merge**:

### Runtime

- Servicio systemd: `openclaw-telegram-bot.service` (bot Python directo en host, sin Docker)
- Policy viva: `/opt/automation/agents/openclaw/broker/restricted_operator_policy.json`
- LLM local: `qwen2.5:3b` vía Ollama en `http://127.0.0.1:11440/v1/chat/completions`
- Secretos: `/etc/davlos/secrets/openclaw`
- Vault Obsidian: `vault_root` configurado en policy bajo `vault_inbox.vault_root`

### Capacidades por fase

| Fase | Descripción | Estado |
|---|---|---|
| 1-3 | Inbox write, draft promote, report promote | Completa, en main |
| 4 | Capa conversacional Obsidian (intents locales) | Completa, en main |
| 5 | Vault read chat (E1 básico, búsqueda por nombre) | Completa, en main |
| 6 | Higiene operativa y UX (errores conversacionales, artefactos pipeline) | Completa, en main |
| 7 | Modo agentico A/B/C/D (wake persistente, confirmaciones, TTL) | Completa, en main |
| 8 | Vault CRUD E1-E4 (leer, explorar, crear, archivar) | Completa, rama `feat/phase8-vault-crud` |
| 9 | Sandbox modo libre + E5/E6 (editar, mover notas; LLM con contexto vault) | Completa, rama `feat/phase8-vault-crud` |

### Acciones broker registradas

`action.health.general.v1`, `action.logs.read.v1`, `action.webhook.trigger.v1`,
`action.openclaw.restart.v1`, `action.dropzone.write.v1`, `action.inbox.write.v1`,
`action.draft.promote.v1`, `action.report.promote.v1`, `action.note.create.v1`,
`action.note.archive.v1`, `action.note.edit.v1`, `action.note.move.v1`

### Sandbox mode (Phase 9)

- Activación: `activa modo libre` / `libera openclaw` / `sandbox on`
- Desactivación: `sal del sandbox` / `modo normal` / `sandbox off`
- En sandbox: mensajes enrutados a `qwen2.5:3b` con historial de sesión e inyección de contexto vault
- LLM puede ejecutar acciones vault via tags `<action>{...}</action>` sin confirmación adicional
- Pipeline artifacts (`STAGED_INPUT.md`, `REPORT_INPUT.md`) excluidos de todos los listados públicos

### Archivos clave

- `scripts/agents/openclaw/restricted_operator/telegram_bot.py` — bot principal
- `scripts/agents/openclaw/restricted_operator/actions.py` — broker actions (incluyendo E3-E6)
- `scripts/agents/openclaw/restricted_operator/policy.py` — PolicyStore
- `scripts/agents/openclaw/vault_browser.py` — navegación read-only del vault
- `scripts/agents/openclaw/llm_agent.py` — SandboxLLMAgent (Phase 9)
- `scripts/agents/openclaw/vault_artifact_reader.py` — lector de artefactos pipeline
- `templates/openclaw/restricted_operator_policy.json` — plantilla de policy

### Operación

```bash
# Estado del servicio
systemctl status openclaw-telegram-bot.service

# Restart
sudo systemctl restart openclaw-telegram-bot.service

# Tests
cd /opt/control-plane && python3 -m unittest discover -s tests/restricted_operator -p "test_*.py"
```

### Límites vigentes

- Sin UI web; operación principal por consola + Telegram
- Hardening final de egress no declarado cerrado
- `action.note.edit.v1` y `action.note.move.v1` requieren habilitarse en policy de producción

## Documentos clave

### OpenClaw — Fases por funcionalidad

- `docs/features/telegram-obsiclaw/PHASE_1_INBOX_WRITE.md`
- `docs/features/telegram-obsiclaw/PHASE_2_DRAFT_PROMOTE.md`
- `docs/features/telegram-obsiclaw/PHASE_3_REPORT_PROMOTE.md`
- `docs/features/telegram-obsiclaw/PHASE_4_OBSIDIAN_CONVERSATIONAL_LAYER.md`
- `docs/features/telegram-obsiclaw/PHASE_5_VAULT_READ_CHAT_MVP.md`
- `docs/features/telegram-obsiclaw/PHASE_6_OPERATIONAL_HYGIENE_AND_UX.md`
- `docs/features/telegram-obsiclaw/PHASE_7_AGENTIC_MODE.md`
- `docs/features/telegram-obsiclaw/PHASE_8_VAULT_CRUD.md`
- `docs/features/telegram-obsiclaw/PHASE_9_SANDBOX_MODE.md`

### Infraestructura y seguridad

- `docs/ARCHITECTURE.md`
- `docs/AGENTS.md`
- `docs/INFERENCE_GATEWAY_OLLAMA_MVP.md`
- `docs/AGENT_ZONE_SECURITY_MVP.md`
- `docs/OPENCLAW_SECURITY_BOOTSTRAP_MVP.md`
- `docs/OPENCLAW_HOST_SECRETS_CONTRACT_MVP.md`
- `runbooks/OPENCLAW_DEPLOY_MVP.md`
- `runbooks/OPENCLAW_ROLLBACK_MVP.md`

### n8n

- `runbooks/N8N_PRECHECKS_EXECUTION.md`
- `runbooks/N8N_BACKUP_AND_ROLLBACK_MINIMUM.md`
- `runbooks/N8N_MIGRATION_WINDOW_PLAN.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`

Nota:
Algunos documentos conservan contexto histórico y deben leerse con fecha y alcance. La verdad operativa actual de `n8n` queda reflejada en `evidence/FASE_4_ESTADO.md` y en las evidencias recientes de prechecks. La verdad actual de `OpenClaw` (2026-04-17): bot Python en systemd, broker con policy viva y auditoría, Telegram como canal conversacional con vault CRUD completo (Fases 1-9), sandbox mode con LLM local `qwen2.5:3b`, y pipeline artifacts excluidos de listados públicos. El hardening final de egress no se declara cerrado en este `README`.

## Regla base

Este repositorio documenta y prepara cambios.
No debe usarse para introducir secretos ni para asumir que un diseño documental ya equivale a estado operativo real.
