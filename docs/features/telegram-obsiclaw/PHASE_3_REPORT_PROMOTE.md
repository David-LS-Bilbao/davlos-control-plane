# Phase 3 — action.report.promote.v1
**Fecha:** 2026-04-14 | **Rama:** feat/obsi-claw-agent-operativo-gate-0

## Decisión técnica elegida

**Bridge directo con fuente de verdad en `capture_status` de la nota origen. `STAGED_INPUT.md` no se consume.**

La acción `action.report.promote.v1` lee una nota existente de `Agent/Inbox_Agent/`,
valida que tenga `capture_status: "promoted_to_draft"`, escribe `REPORT_INPUT.md` en
el mismo directorio para el pipeline de report (usando `build_document()` del helper),
y marca la nota origen como `promoted_to_report`.

Se eligió **no consumir ni requerir `STAGED_INPUT.md`** porque:
- La nota en `Agent/Inbox_Agent/` con `capture_status` es la fuente de verdad atómica y
  determinista para el ciclo de vida: `pending_triage` → `promoted_to_draft` → `promoted_to_report`.
- `STAGED_INPUT.md` puede haber sido consumido por el pipeline de draft antes de que el
  operador invoque report.promote; depender de su presencia o ausencia introduce una
  carrera entre el pipeline y el broker que no es deseable en MVP.
- Mantiene el mismo patrón que Phase 2 (fuente de verdad = frontmatter, no archivos
  de staging efímeros).

Se descartó:
- Requerir que `STAGED_INPUT.md` haya sido consumido antes de promover a report
  (dependencia opaca del pipeline; no verificable de forma determinista desde el broker).
- Consumir/eliminar `STAGED_INPUT.md` como parte de esta acción
  (introduce efecto secundario sobre un archivo que pertenece al pipeline; riesgo de
  corrupción si el pipeline no procesó aún).
- Crear carpeta separada `draft/` o `report/` fuera de vault
  (viola el principio de no crear storage paralelo).

## Archivos tocados

| Archivo | Acción | Método |
|---------|--------|--------|
| `scripts/agents/openclaw/vault_report_promote_bridge.py` | NUEVO | Write directo en repo |
| `scripts/agents/openclaw/restricted_operator/actions.py` | EDITADO | Edit directo en repo |
| `scripts/agents/openclaw/restricted_operator/telegram_bot.py` | EDITADO | Edit directo en repo |
| `templates/openclaw/restricted_operator_policy.json` | EDITADO | Edit directo en repo |
| `tests/restricted_operator/test_report_promote_action.py` | NUEVO | Write directo en repo |
| `docs/features/telegram-obsiclaw/PHASE_3_REPORT_PROMOTE.md` | NUEVO | Write directo en repo |

Archivos explícitamente no tocados:
- `scripts/agents/openclaw/vault_inbox_bridge.py` — sin cambios
- `scripts/agents/openclaw/vault_draft_promote_bridge.py` — solo importado, no modificado
- `scripts/agents/openclaw/restricted_operator/models.py` — sin cambios
- `scripts/agents/openclaw/restricted_operator/policy.py` — sin cambios
- `scripts/agents/openclaw/restricted_operator/broker.py` — sin cambios
- `scripts/agents/openclaw/restricted_operator/audit.py` — sin cambios
- `scripts/helpers/openclaw_manual_promotion_helper.py` — solo importado, no modificado
- `scripts/helpers/openclaw_vault_inbox_writer.py` — solo importado, no modificado
- `scripts/console/davlos-vpn-console.sh` — no tocado
- `scripts/agents/openclaw/activate_inbox_write.py` — no tocado
- systemd units — no tocados
- secretos — no tocados
- `obsi-claw-AI_agent` — no tocado

## Parámetros aceptados por `action.report.promote.v1`

| Parámetro | Tipo | Requerido | Límite | Descripción |
|-----------|------|-----------|--------|-------------|
| `note_name` | string | Sí | 256 chars | Nombre exacto del archivo en Agent/Inbox_Agent/ |

`vault_root` NO es un parámetro de la acción. Viene de `vault_inbox.vault_root` de la policy.

## Validaciones aplicadas

1. `vault_inbox.vault_root` debe estar configurado y ser ruta absoluta.
2. `Agent/Inbox_Agent/` debe existir, sin symlinks.
3. `note_name` debe coincidir con el patrón `^\d{8}T\d{6}Z_inbox_[\w.\-]+\.md$`.
4. La nota debe existir como archivo regular (no symlink).
5. El frontmatter debe tener `capture_status: "promoted_to_draft"` — no se puede reportar una nota `pending_triage` ni una ya `promoted_to_report`.
6. No debe existir `REPORT_INPUT.md` previo (create-only atómico vía O_CREAT|O_EXCL).
7. La nota debe tener `run_id` válido en frontmatter.

Si cualquiera de estas validaciones falla, la acción aborta sin efecto secundario y devuelve código de error específico. Si la escritura de `REPORT_INPUT.md` tiene éxito pero el update del frontmatter falla, se hace rollback eliminando `REPORT_INPUT.md`.

## Cómo se audita

Dos capas, idéntico patrón a Phase 2:

1. **Broker audit (JSONL)** — `restricted_operator.jsonl`
   - Evento: `action_executed` con `audit_params`:
     - `note_name`
   - El cuerpo de la nota **nunca** se escribe en el audit log.

2. **Confirmación Telegram**
   - Evento `confirmation_requested` con `note_name`, `summary`.
   - Evento `confirmation_accepted` o `confirmation_rejected`.
   - Evento `action_executed` o `action_failed` post-ejecución.

## Evidencia que deja en vault

1. **`REPORT_INPUT.md`** en `Agent/Inbox_Agent/` — archivo de handoff para el pipeline report
   - Contiene frontmatter con `operation: report.write`, `run_id`, `report_title`
   - Contiene cuerpo extraído de la sección `## Captura` de la nota origen
   - Incluye `source_refs` con referencia `inbox:<note_name>`

2. **Nota origen actualizada** — `capture_status` cambia de `"promoted_to_draft"` a `"promoted_to_report"`.

`STAGED_INPUT.md` no es tocado por esta acción.

## Interfaz Telegram

### Listar notas reportables

```
/report_promote
```

Muestra hasta 10 notas con `capture_status: "promoted_to_draft"`, ordenadas newest-first.

### Promover una nota a report

```
/report_promote note=<nombre_archivo>
```

Ejemplo:

```
/report_promote note=20260413T100000Z_inbox_tg-001.md
```

Flujo:
1. Operador envía `/report_promote note=...`
2. Bot muestra: `report.promote | note=...`
3. Operador responde `si` → `REPORT_INPUT.md` creado, nota marcada `promoted_to_report`.
4. Operador responde `no` → cancelado sin efecto.

Requiere `operator.write` permission. Viewers no pueden invocarla.

## Ciclo de vida completo validado

```
pending_triage
    │
    ▼  /draft_promote note=<N>
promoted_to_draft          ← STAGED_INPUT.md creado
    │
    ▼  /report_promote note=<N>
promoted_to_report         ← REPORT_INPUT.md creado
```

Cada transición requiere confirmación explícita del operador y queda auditada.
Transiciones inversas o salteadas son rechazadas por validación de estado.

## Deuda técnica abierta tras cerrar MVP de 3 workflows

| ID | Deuda | Prioridad | Notas |
|----|-------|-----------|-------|
| D-1 | Limpieza de `STAGED_INPUT.md` tras procesamiento del pipeline | Baja | El pipeline de draft debería eliminar `STAGED_INPUT.md` una vez creada la nota draft. Si no lo hace, se acumula. Decisión explícita: no limpiar desde el broker para evitar interferencia. |
| D-2 | `REPORT_INPUT.md` huérfano si pipeline de report no consume | Baja | Mismo patrón que `STAGED_INPUT.md`. El pipeline es responsable de consumir. |
| D-3 | TTL automático de draft si no se reporta en N minutos | Baja | Documentado en GATE_0 como hardening posterior. No bloquea MVP. |
| D-4 | Validación de ownership de notas (multitenant) | Baja | Hoy el sistema es single-operator (davlos-operator). Si se añaden operadores, el `note_name` debería validar propietario. |
| D-5 | Comando `/inbox_list` independiente | Muy baja | Hoy `/draft_promote` sin args lista notas en `pending_triage`. Podría tener su propio comando. |
| D-6 | Helper readonly: nuevos modos `inbox_status`, `draft_status`, `report_status` | Muy baja | Los modos existentes de `davlos-openclaw-readonly.sh` no filtran por estado de ciclo de vida. |

Ninguna de estas deudas bloquea el MVP de 3 workflows.

## Comandos de validación

### Compilación

```bash
RO=/opt/control-plane/scripts/agents/openclaw/restricted_operator
python3 -m py_compile ${RO}/actions.py && echo "actions OK"
python3 -m py_compile ${RO}/telegram_bot.py && echo "telegram_bot OK"
python3 -m py_compile /opt/control-plane/scripts/agents/openclaw/vault_report_promote_bridge.py && echo "bridge OK"
```

### Tests

```bash
cd /opt/control-plane
python3 -m unittest tests.restricted_operator.test_report_promote_action -v
# Esperado: 24 tests OK
python3 -m unittest tests.restricted_operator.test_draft_promote_action -v
# Esperado: 20 tests OK
```

### Smoke test del bridge

```bash
cd /opt/control-plane
python3 -c "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, 'scripts/agents/openclaw')
from vault_report_promote_bridge import invoke_report_promote, list_reportable_notes

with tempfile.TemporaryDirectory() as td:
    vault = Path(td) / 'vault'
    inbox = vault / 'Agent' / 'Inbox_Agent'
    inbox.mkdir(parents=True)

    note_name = '20260414T100000Z_inbox_smoke.md'
    (inbox / note_name).write_text('''---
managed_by: obsi-claw-AI_agent
agent_zone: Agent/Inbox_Agent
run_id: \"smoke\"
created_at_utc: \"2026-04-14T10:00:00Z\"
updated_at_utc: \"2026-04-14T10:00:00Z\"
source_refs: []
capture_status: \"promoted_to_draft\"
---

# Smoke Test Report

## Captura

Body text for smoke test.

## Trazabilidad

- operation: inbox.write
''')

    notes = list_reportable_notes(vault_root=str(vault))
    print('Reportable notes:', notes)

    result = invoke_report_promote(vault_root=str(vault), note_name=note_name)
    print('Report result:', result)
    print('REPORT_INPUT.md exists:', (inbox / 'REPORT_INPUT.md').exists())
    print('Source status updated:', 'promoted_to_report' in (inbox / note_name).read_text())
    print('OK')
"
```

### Test end-to-end (Telegram)

```
# Listar notas en estado promoted_to_draft:
/report_promote
# -> Muestra lista de notas listas para report

# Promover una nota:
/report_promote note=20260413T100000Z_inbox_tg-001.md
# -> Responde: Acción interpretada: report.promote | note=...
# Escribir: si
# -> Responde: Nota promovida a report.
```

### Habilitar la acción en runtime

```bash
python3 /opt/control-plane/scripts/agents/openclaw/restricted_operator/cli.py \
  --policy /opt/automation/agents/openclaw/broker/restricted_operator_policy.json \
  enable --action-id action.report.promote.v1 --operator-id davlos-operator
```

### Auditar el flujo

```bash
bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh broker_audit_recent
```

---

**Creado:** 2026-04-14
**Rama:** feat/obsi-claw-agent-operativo-gate-0
**Estado:** MVP cerrado — 3 workflows completos (inbox → draft → report)
