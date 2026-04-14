# Phase 2 — action.draft.promote.v1
**Fecha:** 2026-04-13 | **Rama:** feat/obsi-claw-agent-operativo-gate-0

## Decisión técnica elegida

**Bridge directo con update controlado de capture_status.**

La acción `action.draft.promote.v1` lee una nota existente de `Agent/Inbox_Agent/`,
valida que tenga `capture_status: "pending_triage"`, escribe `STAGED_INPUT.md` para
el pipeline de draft (reutilizando `build_document()` del manual promotion helper),
y marca la nota origen como `promoted_to_draft`.

Se eligió actualizar `capture_status` en la nota origen (en vez de un marker file
separado) porque:
- Es la forma más simple de prevenir doble promoción
- Es una transición de un solo campo, auditable y determinista
- La nota pertenece al agente y el campo ya existe para este propósito

Se descartó:
- Crear archivos marker en subdirectorio `.promoted/` (complejidad innecesaria)
- Llamar al helper vía subprocess (abre shell indirecta)
- Escribir directamente la nota draft final (el pipeline del agente se encarga)

## Archivos tocados

| Archivo | Acción | Método |
|---------|--------|--------|
| `scripts/agents/openclaw/vault_draft_promote_bridge.py` | NUEVO | Write directo en repo |
| `scripts/agents/openclaw/restricted_operator/actions.py` | EDITADO | Edit directo en repo |
| `scripts/agents/openclaw/restricted_operator/telegram_bot.py` | EDITADO | Edit directo en repo |
| `templates/openclaw/restricted_operator_policy.json` | EDITADO | Edit directo en repo |
| `tests/restricted_operator/test_draft_promote_action.py` | NUEVO | Write directo en repo |
| `docs/features/telegram-obsiclaw/PHASE_2_DRAFT_PROMOTE.md` | NUEVO | Write directo en repo |

Archivos explícitamente no tocados:
- `scripts/agents/openclaw/vault_inbox_bridge.py` — sin cambios
- `scripts/agents/openclaw/restricted_operator/models.py` — sin cambios
- `scripts/agents/openclaw/restricted_operator/policy.py` — sin cambios
- `scripts/helpers/openclaw_manual_promotion_helper.py` — solo importado, no modificado
- `scripts/helpers/openclaw_vault_inbox_writer.py` — solo importado, no modificado
- `scripts/console/davlos-vpn-console.sh` — no tocado
- systemd units — no tocados
- secretos — no tocados
- `obsi-claw-AI_agent` — no tocado

## Parámetros aceptados por `action.draft.promote.v1`

| Parámetro | Tipo | Requerido | Límite | Descripción |
|-----------|------|-----------|--------|-------------|
| `note_name` | string | Sí | 256 chars | Nombre exacto del archivo en Agent/Inbox_Agent/ |

`vault_root` NO es un parámetro de la acción. Viene de `vault_inbox.vault_root` de la policy.

## Validaciones aplicadas

1. `vault_inbox.vault_root` debe estar configurado y ser ruta absoluta
2. `Agent/Inbox_Agent/` debe existir, sin symlinks
3. `note_name` debe coincidir con el patrón `^\d{8}T\d{6}Z_inbox_[\w.\-]+\.md$`
4. La nota debe existir como archivo regular (no symlink)
5. El frontmatter debe tener `capture_status: "pending_triage"`
6. No debe existir `STAGED_INPUT.md` previo (conflicto de staging)
7. La nota debe tener `run_id` válido en frontmatter

## Cómo se audita

Dos capas:

1. **Broker audit (JSONL)** — `restricted_operator.jsonl`
   - Evento: `action_executed` con `audit_params`:
     - `note_name`
   - El cuerpo de la nota **nunca** se escribe en el audit log

2. **Confirmación Telegram**
   - Evento `confirmation_requested` con `note_name`, `summary`
   - Evento `confirmation_accepted` o `confirmation_rejected`
   - Evento `action_executed` o `action_failed` post-ejecución

## Evidencia que deja en vault

1. **`STAGED_INPUT.md`** en `Agent/Inbox_Agent/` — archivo de staging para el pipeline draft
   - Contiene frontmatter con `operation: draft.write`, `run_id`, `draft_title`
   - Contiene el cuerpo extraído de la nota original
   - Incluye `source_refs` con referencia `inbox:<note_name>`

2. **Nota origen actualizada** — `capture_status` cambia de `"pending_triage"` a `"promoted_to_draft"`

## Interfaz Telegram

### Listar notas promotables
```
/draft_promote
```
Muestra hasta 10 notas con `capture_status: "pending_triage"`, ordenadas newest-first.

### Promover una nota específica
```
/draft_promote note=<nombre_archivo>
```

Ejemplo:
```
/draft_promote note=20260413T100000Z_inbox_tg-001.md
```

Flujo:
1. Operador envía `/draft_promote note=...`
2. Bot muestra: `draft.promote | note=...`
3. Operador responde `si` → promoción ejecuta → `Nota promovida a draft.`
4. Operador responde `no` → cancelado sin efecto

Requiere `operator.write` permission. Viewers no pueden invocarla.

## Qué queda pendiente para Fase 3 (`report.promote`)

- `action.report.promote.v1` — promover draft a report en `Agent/Reports_Agent/`
- Consumir y eliminar `STAGED_INPUT.md` tras procesamiento exitoso del pipeline
- Validar que la nota tenga estado `promoted_to_draft` antes de report
- Considerar hardening de ownership de notas (deuda identificada, no bloquea Phase 2)
- Considerar `/inbox_list` como comando independiente (hoy integrado en `/draft_promote` sin args)

## Comandos de validación

### Compilación

```bash
RO=/opt/control-plane/scripts/agents/openclaw/restricted_operator
python3 -m py_compile ${RO}/actions.py && echo "actions OK"
python3 -m py_compile ${RO}/telegram_bot.py && echo "telegram_bot OK"
python3 -m py_compile /opt/control-plane/scripts/agents/openclaw/vault_draft_promote_bridge.py && echo "bridge OK"
```

### Tests

```bash
cd /opt/control-plane
python3 -m unittest tests.restricted_operator.test_draft_promote_action -v
```

### Smoke test del bridge

```bash
cd /opt/control-plane
python3 -c "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, 'scripts/agents/openclaw')
from vault_draft_promote_bridge import invoke_draft_promote, list_promotable_notes

with tempfile.TemporaryDirectory() as td:
    vault = Path(td) / 'vault'
    inbox = vault / 'Agent' / 'Inbox_Agent'
    inbox.mkdir(parents=True)

    # Create a fake inbox note
    note_name = '20260413T100000Z_inbox_smoke.md'
    (inbox / note_name).write_text('''---
managed_by: obsi-claw-AI_agent
agent_zone: Agent/Inbox_Agent
run_id: \"smoke\"
created_at_utc: \"2026-04-13T10:00:00Z\"
updated_at_utc: \"2026-04-13T10:00:00Z\"
source_refs: []
capture_status: \"pending_triage\"
---

# Smoke Test

## Captura

Body text for smoke test.

## Trazabilidad

- operation: inbox.write
''')

    # List
    notes = list_promotable_notes(vault_root=str(vault))
    print('Promotable notes:', notes)

    # Promote
    result = invoke_draft_promote(vault_root=str(vault), note_name=note_name)
    print('Promote result:', result)
    print('STAGED_INPUT.md exists:', (inbox / 'STAGED_INPUT.md').exists())
    print('Source status updated:', 'promoted_to_draft' in (inbox / note_name).read_text())
    print('OK')
"
```

### Test end-to-end (Telegram)

```
# Listar notas promotables:
/draft_promote
# -> Muestra lista de notas con pending_triage

# Promover una nota:
/draft_promote note=20260413T100000Z_inbox_tg-001.md
# -> Responde: Acción interpretada: draft.promote | note=...
# Escribir: si
# -> Responde: Nota promovida a draft.
```

### Habilitar la acción en runtime

```bash
python3 /opt/control-plane/scripts/agents/openclaw/restricted_operator/cli.py \
  --policy /opt/automation/agents/openclaw/broker/restricted_operator_policy.json \
  enable --action-id action.draft.promote.v1 --operator-id davlos-operator
```
