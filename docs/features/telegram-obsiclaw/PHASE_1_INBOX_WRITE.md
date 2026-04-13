# Phase 1 — action.inbox.write.v1
**Fecha:** 2026-04-13 | **Rama:** feat/obsi-claw-agent-operativo-gate-0

## Decisión técnica elegida

**Bridge directo hacia `openclaw_vault_inbox_writer`.**

La acción `action.inbox.write.v1` no crea ningún dominio de almacenamiento paralelo.
Escribe directamente en `vault_root/Agent/Inbox_Agent/` reutilizando las funciones
de sanitización y escritura del writer ya existente y probado.

El módulo `vault_inbox_bridge.py` encapsula la llamada: ajusta `sys.path` para importar
el writer sin duplicar lógica, y expone una única función cerrada `invoke_inbox_write()`.
El `vault_root` viene de la policy, no de parámetros libres del caller.

Se descartó explícitamente:
- Llamar al writer vía subprocess (abre shell indirecta)
- Duplicar las sanitizaciones (ya probadas en tests/helpers/)
- Escribir en un dominio paralelo tipo `/opt/automation/agents/openclaw/inbox/`

## Archivos tocados

| Archivo | Acción | Método |
|---------|--------|--------|
| `scripts/agents/openclaw/vault_inbox_bridge.py` | EXISTENTE (sin cambios) | — |
| `templates/openclaw/restricted_operator_policy.json` | EXISTENTE (sin cambios) | — |
| `scripts/agents/openclaw/restricted_operator/models.py` | EDITADO | Edit directo en repo |
| `scripts/agents/openclaw/restricted_operator/policy.py` | EDITADO | Edit directo en repo |
| `scripts/agents/openclaw/restricted_operator/actions.py` | EDITADO | Edit directo en repo |
| `scripts/agents/openclaw/restricted_operator/telegram_bot.py` | EDITADO | Edit directo en repo |
| `tests/restricted_operator/test_inbox_write_action.py` | NUEVO | Write directo en repo |
| `docs/features/telegram-obsiclaw/PHASE_1_INBOX_WRITE.md` | EDITADO | Edit directo en repo |

Todos los cambios se aplican directamente sobre los archivos del repo con diffs auditables.
No se requiere `sudo` ni ningún script de parcheo.

## Parámetros aceptados por `action.inbox.write.v1`

| Parámetro | Tipo | Requerido | Límite | Descripción |
|-----------|------|-----------|--------|-------------|
| `run_id` | string | Sí | 64 chars | Identificador único de la captura (alfanumérico + `.`, `-`) |
| `capture_title` | string | Sí | 160 bytes UTF-8 | Título de una línea, sin control characters |
| `capture_body` | string | Sí | 4096 bytes (broker) / 16KB (writer) | Cuerpo de la captura |
| `source_refs` | list[str] | No | — | Referencias opcionales a fuentes |

`vault_root` NO es un parámetro de la acción. Viene del campo `vault_inbox.vault_root` de la policy.

## Cómo se valida

1. El broker valida que `vault_inbox.vault_root` no esté vacío. Si lo está → `not_configured`.
2. El bridge pasa por las mismas funciones de sanitización del `openclaw_vault_inbox_writer`:
   - `sanitize_component(run_id)` → rechaza path traversal y chars no permitidos
   - `sanitize_single_line_text(capture_title)` → rechaza null bytes, newlines, exceso de bytes
   - `sanitize_body_text(capture_body)` → rechaza null bytes, vacío, exceso de bytes
   - `sanitize_source_refs(refs)` → rechaza null bytes, newlines, valores vacíos
3. La ruta destino se resuelve con `strict=True` y `assert_no_symlinks`. Si `Agent/Inbox_Agent/` no existe → `destination_missing`.
4. La escritura usa `O_CREAT | O_EXCL` → si la nota ya existe → `write_failed`. Semántica create-only garantizada.

## Cómo se audita

Dos capas de auditoría:

1. **Broker audit (JSONL)** — `restricted_operator.jsonl`
   - Evento: `action_executed` con `audit_params`:
     - `run_id`, `capture_title`, `body_bytes`, `source_refs_count`
     - El cuerpo (`capture_body`) **nunca se escribe en el audit log**
   - Trazable vía `/audit_tail` o helper readonly

2. **Confirmación Telegram** — antes de ejecutar:
   - Evento `confirmation_requested` con `run_id`, `capture_title`, `body_bytes`
   - Evento `confirmation_accepted` o `confirmation_rejected`

## Interfaz Telegram

Slash command nuevo:

```
/inbox_write run_id=<id> title=<titulo> :: <captura>
```

Separador `::` permite que el cuerpo contenga espacios sin URL-encoding.

Ejemplos:

```
/inbox_write run_id=tg-001 title=Error+en+prod :: El servicio X cae al recibir payloads vacios en el endpoint /api/v2/ingest

/inbox_write run_id=obs-042 title=Nota+operativa :: Revisado UFW: regla 18789 presente pero no confirmada en runtime. Requiere validacion post-restart.
```

Flujo completo:
1. Operador envía `/inbox_write ...`
2. Bot muestra summary del pending: `inbox.write | run_id=... | title=... | body=NNN B`
3. Operador responde `si` → acción ejecuta → respuesta: `Captura guardada.\nnota: <nombre_archivo>`
4. Operador responde `no` → cancelado sin efecto

Requiere `operator.write` permission. Operadores `viewer` no pueden invocarla.

## Qué queda pendiente para draft/report

`action.draft.promote.v1` — promover inbox a draft:
- Lee una entrada existente de `Agent/Inbox_Agent/`
- Llama a `openclaw_manual_promotion_helper.py prepare draft`
- Reutiliza `openclaw_vault_report_writer.py` para la escritura en draft
- Requiere validar que el estado sea `pending_triage` (no `drafted`)

`action.report.promote.v1` — promover draft a report:
- Lee una entrada existente de `Agent/Inbox_Agent/` (en draft state)
- Llama a `openclaw_vault_report_writer.py`
- Escribe en `Agent/Reports_Agent/`
- Requiere validar que el estado sea `drafted` (no `reported`)

Ambas acciones deben seguir el mismo patrón bridge: sin shell, create-only, validación de state, auditoría.

## Comandos de validación

### Smoke test del bridge (siempre disponible)

```bash
cd /opt/control-plane
python3 -c "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, 'scripts/agents/openclaw')
from vault_inbox_bridge import invoke_inbox_write

with tempfile.TemporaryDirectory() as td:
    vault = Path(td) / 'vault'
    (vault / 'Agent' / 'Inbox_Agent').mkdir(parents=True)
    result = invoke_inbox_write(
        vault_root=str(vault),
        run_id='smoke-001',
        capture_title='Test capture',
        capture_body='Body text here.',
    )
    print(result)
    print('OK:', Path(result['note_path']).exists())
"
```

### Compilación

```bash
RO=/opt/control-plane/scripts/agents/openclaw/restricted_operator
python3 -m py_compile ${RO}/models.py && echo "models OK"
python3 -m py_compile ${RO}/policy.py && echo "policy OK"
python3 -m py_compile ${RO}/actions.py && echo "actions OK"
python3 -m py_compile ${RO}/telegram_bot.py && echo "telegram_bot OK"
```

### Tests

```bash
cd /opt/control-plane
python3 -m unittest tests.restricted_operator.test_inbox_write_action -v
```

Resultado esperado: 12 tests pasando.

### Configurar vault_root antes de habilitar

```bash
# Editar la policy runtime en el VPS (con el vault_root real):
# /opt/automation/agents/openclaw/broker/restricted_operator_policy.json
# -> vault_inbox.vault_root = "/ruta/real/al/vault"

# Habilitar la acción:
python3 /opt/control-plane/scripts/agents/openclaw/restricted_operator/cli.py \
  --policy /opt/automation/agents/openclaw/broker/restricted_operator_policy.json \
  enable --action-id action.inbox.write.v1 --operator-id davlos-operator
```

### Test end-to-end (Telegram)

```
# Con bot activo:
/inbox_write run_id=e2e-001 title=Test+E2E :: Esta es una captura de prueba end-to-end.
# -> Responde: Acción interpretada: inbox.write | run_id=e2e-001 | ...
# Escribir: si
# -> Responde: Captura guardada. nota: 20260413T..._inbox_e2e-001.md
```

Verificar con helper readonly:
```bash
sudo bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh broker_audit_recent
```
