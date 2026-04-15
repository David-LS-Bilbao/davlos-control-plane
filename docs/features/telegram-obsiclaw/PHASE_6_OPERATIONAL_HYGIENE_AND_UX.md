# Phase 6 — Operational Hygiene and Conversational UX MVP

## Decisión técnica elegida

Mejoras mínimas y cerradas sobre código existente, sin abrir nuevas mutaciones ni nueva arquitectura:

- **Un módulo nuevo read-only** (`vault_artifact_reader.py`) para inspeccionar STAGED_INPUT.md y REPORT_INPUT.md sin mutarlos.
- **Funciones de render nuevas** en `assistant_responses.py` para errores operativos ya existentes y para los 3 intents nuevos.
- **Intents conversacionales cerrados** añadidos al matcher local existente en `telegram_bot.py` (mismo patrón que Phases 4 y 5).
- **Mensajes de error mejorados** para `staging_conflict`, `report_conflict`, `not_promotable`, `not_reportable`, `not_found` y referencia ambigua.
- **Enriquecimiento de estado de nota**: `_obsidian_show_status` ahora llama a `get_note_status` para obtener `created_at_utc` real (antes era `"?"`) y añade `source_dir`.

Sin tocar: bridges, broker, policy, systemd, secretos, `obsi-claw-AI_agent`, ni Phases 1-5.

---

## Intents añadidos

| Frase de ejemplo | Intent detectado | Tipo |
|---|---|---|
| "qué puedes hacer con obsidian" | `obsidian.help` | read-only |
| "ayuda obsidian" | `obsidian.help` | read-only |
| "ayuda vault" | `obsidian.help` | read-only |
| "qué artefactos pendientes hay" | `obsidian.pending_artifacts` | read-only |
| "hay artefactos pendientes" | `obsidian.pending_artifacts` | read-only |
| "que hay en cola" | `obsidian.pending_artifacts` | read-only |
| "qué bloquea la ultima" | `obsidian.what_blocks` | read-only |
| "qué bloquea <ref>" | `obsidian.what_blocks` | read-only |
| "por qué no puedo promover <ref>" | `obsidian.what_blocks` | read-only |

Todos los intents nuevos son **read-only**. No proponen confirmación ni invocan al broker.

---

## Mensajes / UX mejorados

### Errores operativos (antes: `code=...\nerror=...`)

| Código | Mensaje conversacional nuevo |
|---|---|
| `staging_conflict` | "No puedo promover '…' a draft: ya hay un STAGED_INPUT.md pendiente. El pipeline anterior aún no ha procesado ese artefacto." + pistas |
| `report_conflict` | "No puedo promover '…' a report: ya hay un REPORT_INPUT.md pendiente…" + pistas |
| `not_promotable` | "No puedo promover '…' a draft. La nota no está en estado pending_triage." + pistas hacia report o estado |
| `not_reportable` | "No puedo promover '…' a report. La nota no está en estado promoted_to_draft." + pistas hacia draft |
| `not_found` (promote) | "No encontré ninguna nota que coincida con '…' en el inbox." + pistas |

### Referencia ambigua (`render_obsidian_ambiguous`)

Antes: lista plana con "Usa el nombre de archivo exacto…"

Ahora: lista numerada (hasta 5 candidatos) + ejemplo concreto de cómo repetir con nombre exacto:
```
Hay 3 notas que coinciden. Sé más específico para consultar estado:
  1. 20260414T100000Z_inbox_proyecto-A.md
  2. 20260414T100000Z_inbox_proyecto-B.md
  3. 20260414T100000Z_inbox_proyecto-C.md
Repite usando el nombre exacto del archivo. Ejemplo:
  estado de 20260414T100000Z_inbox_proyecto-A.md
```

### Estado de nota (`_obsidian_show_status`)

Antes: `created_at_utc` era siempre `"?"`.

Ahora: llama a `get_note_status` para leer el valor real del frontmatter. Añade campo `directorio: Agent/Inbox_Agent`.

---

## Artefactos que inspecciona (solo lectura)

- `<vault_root>/Agent/Inbox_Agent/STAGED_INPUT.md` — presencia + extracción de `note_name` del frontmatter si existe.
- `<vault_root>/Agent/Inbox_Agent/REPORT_INPUT.md` — ídem.

**No se mutua, no se borra, no se modifica ninguno de los dos archivos.**

---

## Qué queda fuera de alcance

- Limpieza automática de STAGED_INPUT.md o REPORT_INPUT.md.
- Edición de notas.
- Búsqueda semántica o índices persistentes.
- Nuevas acciones mutantes.
- Cambios en policy, systemd o secretos.
- Lectura de contenido de los artefactos (solo se inspecciona presencia y nombre de nota fuente).

---

## Archivos tocados

| Archivo | Cambio |
|---|---|
| `scripts/agents/openclaw/vault_artifact_reader.py` | **NUEVO** — lector read-only de artefactos de pipeline |
| `scripts/agents/openclaw/restricted_operator/assistant_responses.py` | Render functions Phase 6 + mejora `render_obsidian_ambiguous` + `render_obsidian_note_status_v2` |
| `scripts/agents/openclaw/restricted_operator/telegram_bot.py` | 3 intents nuevos + `_render_promote_error` + mejora `_obsidian_show_status` + import `get_note_status`/`read_pending_artifacts` |
| `tests/restricted_operator/test_phase6_operational_hygiene.py` | **NUEVO** — 49 tests de la fase |
| `tests/restricted_operator/test_phase4_obsidian_conversational.py` | 1 assertion adaptada al nuevo mensaje conversacional |
| `tests/restricted_operator/test_report_promote_action.py` | 1 assertion adaptada al nuevo mensaje conversacional |

## Archivos explícitamente no tocados

- `vault_draft_promote_bridge.py`, `vault_report_promote_bridge.py`, `vault_inbox_bridge.py`
- `actions.py`, `broker.py`, `policy.py`, `models.py`, `audit.py`
- `intent_router.py`, `intent_schema.py`, `obsidian_intent_resolver.py`, `vault_read_chat.py`
- Todo lo de `/home/devops/shadow-control-plane/`
- Systemd, secretos, policy JSON de producción
- `obsi-claw-AI_agent`

---

## Comandos exactos de validación

```bash
# Tests de Phase 6 (49 tests)
cd /opt/control-plane
python3 -m unittest tests/restricted_operator/test_phase6_operational_hygiene.py -v

# Suite completa (251 tests; 2 fallos pre-existentes en test_broker concurrencia)
python3 -m unittest discover -s tests/restricted_operator -p "test_*.py" 2>&1 | grep -E "^(Ran|OK|FAIL)"

# Validación conversacional rápida (frases que deben resolverse)
# Nota: requiere policy real y vault configurado en producción
# Frases a probar en Telegram:
#   ayuda obsidian
#   qué artefactos pendientes hay
#   qué bloquea la ultima
#   estado de <nombre_nota>   ← debe mostrar created_at_utc real y directorio
```

---

## Riesgos abiertos

| Riesgo | Mitigación |
|---|---|
| `vault_artifact_reader.py` ignora errores silenciosamente si el vault no es accesible | Comportamiento correcto: `is_file()` devuelve False → no bloquea |
| Los 2 fallos pre-existentes en `test_broker` (concurrencia de estado) no son de esta fase | Pre-existentes, documentados; no se tocan |
| `get_note_status` puede devolver `created_at_utc: "?"` si el frontmatter no lo tiene | Aceptable; muestra `"?"` igual que antes en ese caso |

---

## Qué NO está implementado todavía

- Integración con `/help` o `/start` para mencionar las nuevas frases obsidian.
- `render_obsidian_conversation_help` no actualizado con los nuevos intents (fuera de alcance de esta fase).
- Lectura del contenido de STAGED_INPUT.md / REPORT_INPUT.md (solo presencia).
- Diagnóstico de por qué el pipeline no ha consumido un artefacto.
