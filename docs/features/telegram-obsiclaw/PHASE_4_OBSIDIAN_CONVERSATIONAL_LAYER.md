# Phase 4 — Obsidian Conversational Layer MVP
**Fecha:** 2026-04-14 | **Rama:** feat/obsi-claw-agent-operativo-gate-0

## Decisión técnica elegida

**Parser local cerrado con tabla de patrones. Sin LLM, sin búsqueda semántica, sin edición libre.**

La capa conversacional es un método `_match_obsidian_intent` que compara texto normalizado (sin acentos, sin puntuación) contra conjuntos fijos de frases y prefijos.  No reemplaza los slash commands existentes.  Los intents detectados se dispatchen a handlers que reutilizan exactamente el mismo `PendingConfirmation` → `_execute_pending_confirmation` flow de Phases 1-3.

Se eligió este enfoque sobre LLM o matching semántico porque:
- No abre superficie de inyección ni salida del perímetro.
- El conjunto de operaciones soportadas es pequeño y bien definido.
- Añadir o quitar frases es un cambio de 1 línea, auditable.
- Sin dependencias de red para la detección de intents.

## Archivos tocados

| Archivo | Acción |
|---------|--------|
| `scripts/agents/openclaw/obsidian_intent_resolver.py` | NUEVO — resolución de referencias a notas |
| `scripts/agents/openclaw/restricted_operator/telegram_bot.py` | EDITADO — `_match_obsidian_intent`, `_handle_obsidian_intent` y sub-handlers |
| `scripts/agents/openclaw/restricted_operator/assistant_responses.py` | EDITADO — renders de Obsidian |
| `tests/restricted_operator/test_phase4_obsidian_conversational.py` | NUEVO — 51 tests |
| `docs/features/telegram-obsiclaw/PHASE_4_OBSIDIAN_CONVERSATIONAL_LAYER.md` | NUEVO |

Archivos explícitamente no tocados:
- `intent_schema.py` — no modificado (schema es solo para intents LLM-validados)
- `intent_router.py` — no modificado
- Phases 1-3: `vault_inbox_bridge.py`, `vault_draft_promote_bridge.py`, `vault_report_promote_bridge.py`
- `actions.py`, `broker.py`, `audit.py`, `policy.py`, `models.py` — sin cambios
- `templates/openclaw/restricted_operator_policy.json` — sin cambios
- systemd, secretos, `obsi-claw-AI_agent` — no tocados

## Intents soportados

| Intent | Tipo | Permiso |
|--------|------|---------|
| `obsidian.list_pending` | lectura | `operator.read` |
| `obsidian.list_report_ready` | lectura | `operator.read` |
| `obsidian.show_note_status` | lectura | `operator.read` |
| `obsidian.capture` | mutación | `operator.write` + `action.inbox.write.v1` habilitada |
| `obsidian.capture_clarify` | aclaración | ninguno |
| `obsidian.promote_to_draft` | mutación | `operator.write` + `action.draft.promote.v1` habilitada |
| `obsidian.promote_to_report` | mutación | `operator.write` + `action.report.promote.v1` habilitada |

## Ejemplos de frases soportadas

### Listar notas pendientes (pending_triage)

```
qué tengo pendiente
notas pendientes
qué hay en inbox
listas para draft
```

### Listar notas listas para report (promoted_to_draft)

```
listas para report
notas en draft
qué está listo para report
notas para report
```

### Consultar estado de una nota

```
estado de tg-001
qué estado tiene myrun
busca la nota 20260414T100000Z_inbox_tg-001.md
dime el estado de ultima
```

### Capturar una nota

```
guarda esta idea: Mi plan :: Revisar los costes del proyecto
anota esto: Reunión :: Hemos acordado subir el precio un 10%
guarda una nota: Próximos pasos :: Punto 1. Punto 2.
```

### Promover la última nota a draft

```
promueve la ultima a draft
promueve tg-001 a draft
promover la última a draft
```

### Promover una nota a report

```
promueve la ultima a report
promueve tg-001 a report
```

## Reglas de resolución de referencias a notas

| Referencia | Estrategia |
|-----------|------------|
| `ultima` / `last` / `la última` | Nota más reciente por nombre de archivo (timestamp) |
| Nombre exacto (`20260414T100000Z_inbox_*.md`) | Búsqueda directa en `Agent/Inbox_Agent/` |
| Token alfanumérico (`tg-001`, `myrun`) | Búsqueda de substring en nombres de archivo, normalizado sin puntuación |

**Nota sobre normalización:** Los guiones (`-`) son puntuación en Unicode y son eliminados por `_normalize_text`. Por tanto, "tg-001" se convierte en "tg001" como token de búsqueda. El resolver normaliza también los nombres de archivo a solo alfanuméricos para la comparación, de modo que "tg001" encuentra "20260414T100000Z_inbox_tg-001.md". Los slash commands (`/draft_promote note=...`) aceptan el nombre exacto con guiones sin normalización.

## Reglas de aclaración

| Situación | Respuesta |
|-----------|-----------|
| Referencia ambigua (múltiples candidatos) | Lista de hasta 5 candidatos + pedir nombre exacto |
| Captura detectada sin `::` | Ejemplo de sintaxis correcta (`título :: cuerpo`) |
| Referencia no encontrada | Mensaje de nota no encontrada |
| vault_root no configurado | Mensaje de configuración pendiente |

## Cómo se audita

Todos los intents (incluyendo conversacionales) generan eventos de auditoría JSONL:
- Lectura: evento `response_generated` con `intent` y preview del texto.
- Mutación: evento `confirmation_requested` → `confirmation_accepted`/`confirmation_rejected` → `action_executed`/`action_failed`.
- Los mismos eventos que generan los slash commands equivalentes (mismo `_execute_pending_confirmation` flow).

El cuerpo de las notas **nunca** se vuelca en el audit log.

## Compatibilidad con slash commands

Los slash commands existentes no se modifican y tienen prioridad en el routing:

```
/inbox_write run_id=<id> title=<titulo> :: <cuerpo>   # sigue funcionando
/draft_promote note=<nombre>                           # sigue funcionando
/report_promote note=<nombre>                          # sigue funcionando
```

Los intents conversacionales solo se evalúan si el mensaje no es un slash command (`/`).

## Qué queda fuera del alcance

- Frases fuera del conjunto definido → `render_conversation_help()` o `render_assistant_fallback()`
- Referencias exactas de archivo con puntuación compleja → usar slash commands
- Lectura libre del vault (contenido de notas)
- Edición de notas existentes
- Búsqueda semántica o por palabras clave dentro del cuerpo de notas
- Creación de notas con `run_id` personalizado desde conversación (auto-generado `tg-{timestamp}`)
- Promoción de notas en lote

## Deuda técnica abierta

| ID | Deuda |
|----|-------|
| D-P4-1 | Frases con acentos en status prefixes: "qué estado tiene" funciona porque `_normalize_text` los elimina, pero los prefixes en `_OBS_STATUS_PREFIXES` son sin acento. Funciona correctamente; documentado para claridad. |
| D-P4-2 | `obsidian.list_pending` y `obsidian.list_draft_ready` comparten el mismo conjunto de datos (pending_triage). Unificados como `list_pending`. Si el negocio diferencia los conceptos, separar en un futuro. |
| D-P4-3 | La aclaración de referencias ambiguas no tiene follow-up de estado: el operador debe reenviar el comando con el nombre exacto. No hay estado de "esperando aclaración" persistido. |
| D-P4-4 | Token search sin hyphens puede generar falsos positivos si existen run_ids muy cortos (ej: "a" matchea todo). En producción los run_ids son suficientemente específicos para evitarlo. |

## Comandos de validación

### Compilación

```bash
python3 -m py_compile scripts/agents/openclaw/obsidian_intent_resolver.py
python3 -m py_compile scripts/agents/openclaw/restricted_operator/telegram_bot.py
python3 -m py_compile scripts/agents/openclaw/restricted_operator/assistant_responses.py
```

### Tests Phase 4

```bash
cd /opt/control-plane
python3 -m unittest tests.restricted_operator.test_phase4_obsidian_conversational -v
# Esperado: 51 tests OK
```

### Suite completa (Phases 2+3+4)

```bash
python3 -m unittest \
  tests.restricted_operator.test_draft_promote_action \
  tests.restricted_operator.test_report_promote_action \
  tests.restricted_operator.test_phase4_obsidian_conversational \
  -v
# Esperado: 95 tests OK
```

### Smoke test del resolver

```bash
python3 -c "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, 'scripts/agents/openclaw')
from obsidian_intent_resolver import resolve_note

with tempfile.TemporaryDirectory() as td:
    inbox = Path(td) / 'vault' / 'Agent' / 'Inbox_Agent'
    inbox.mkdir(parents=True)
    (inbox / '20260414T100000Z_inbox_tg-001.md').write_text(
        '---\nrun_id: \"tg-001\"\ncapture_status: \"pending_triage\"\n---\n# T\n', encoding='utf-8')
    r = resolve_note(str(Path(td) / 'vault'), 'ultima')
    print('ultima:', r)
    r2 = resolve_note(str(Path(td) / 'vault'), 'tg 001')
    print('tg 001 (normalizado):', r2)
    print('OK')
"
```

### Test end-to-end (Telegram)

```
# Lista pendientes:
qué tengo pendiente
# → Notas pendientes: ...

# Capturar:
guarda esta idea: Plan de hoy :: Revisar los costes
# → Acción interpretada: inbox.write | ...
si
# → Captura guardada.

# Promover:
promueve la ultima a draft
# → draft.promote | note=...
si
# → Nota promovida a draft.
```

---

**Creado:** 2026-04-14
**Estado:** MVP Phase 4 cerrado — capa conversacional operativa sobre 3 workflows validados
