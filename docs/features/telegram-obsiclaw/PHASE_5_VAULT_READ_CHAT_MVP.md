# Phase 5 — Vault Conversational Read Chat MVP
**Fecha:** 2026-04-14 | **Rama:** feat/obsi-claw-agent-operativo-gate-0

## Decisión técnica elegida

**Lector local cerrado con búsqueda por substring y filtro de fecha por prefijo de filename.**

Tres operaciones de lectura, ninguna mutación:

| Operación | Estrategia |
|-----------|-----------|
| `list_last_n` | Ordena notas por nombre de archivo (timestamp), devuelve las N primeras |
| `search_notes` | `query.lower() in (title + excerpt).lower()` — substring puro, sin stemming |
| `summarize_today` | Filtra por prefijo YYYYMMDD del nombre de archivo == hoy UTC |

Se eligió este enfoque porque:
- Sin dependencias de red ni LLM.
- La búsqueda por substring es directa, auditable y reproducible.
- El prefijo de fecha en el filename ya actúa como índice temporal gratuito.
- Ningún resultado depende de estado externo ni de modelos.

## Archivos tocados

| Archivo | Acción |
|---------|--------|
| `scripts/agents/openclaw/vault_read_chat.py` | NUEVO — lector local de notas |
| `scripts/agents/openclaw/restricted_operator/telegram_bot.py` | EDITADO — import, trigger sets, matchers, handlers |
| `scripts/agents/openclaw/restricted_operator/assistant_responses.py` | EDITADO — 3 nuevas funciones render |
| `tests/restricted_operator/test_phase5_vault_read_chat.py` | NUEVO — 36 tests |
| `docs/features/telegram-obsiclaw/PHASE_5_VAULT_READ_CHAT_MVP.md` | NUEVO |

## Archivos explícitamente no tocados

- Phases 1-4: `vault_inbox_bridge.py`, `vault_draft_promote_bridge.py`, `vault_report_promote_bridge.py`, `obsidian_intent_resolver.py`
- `actions.py`, `broker.py`, `audit.py`, `policy.py`, `models.py`
- `templates/openclaw/restricted_operator_policy.json`
- systemd, secretos, `obsi-claw-AI_agent`

## Intents añadidos (Phase 5)

| Intent | Tipo | Permiso |
|--------|------|---------|
| `obsidian.list_last_n` | lectura | `operator.read` |
| `obsidian.search_text` | lectura | `operator.read` |
| `obsidian.summary_today` | lectura | `operator.read` |

Todos se dispatchen a través del `_handle_obsidian_intent` ya existente. Sin nuevas rutas de mutación.

## Frases soportadas

### Listar últimas N notas

```
muéstrame las últimas 5 notas
últimas 3 notas
dame las últimas 10
las últimas notas          # default N=5
```

### Búsqueda por texto

```
busca verity
buscar costes
encuentra reunión
buscar Q2
```

**Nota:** `busca nota <ref>` y `busca la nota <ref>` siguen siendo consultas de estado (Phase 4), no búsqueda de texto. El orden de evaluación garantiza que no hay colisión.

### Resumen de lo guardado hoy

```
resúmeme lo guardado hoy
notas de hoy
qué guardé hoy
resumen de hoy
guardado hoy
```

## Directorios leídos

- `Agent/Inbox_Agent/` — notas de captura (Phases 1-4)
- `Agent/Reports_Agent/` — notas de report

Solo archivos con patrón de timestamp `YYYYMMDDTHHMMSSZ_*.md`. El `vault_root` se toma de `policy.vault_inbox.vault_root` (misma config que Phases 1-4).

## Campos extraídos por nota

| Campo | Fuente |
|-------|--------|
| `note_name` | nombre de archivo |
| `source_dir` | directorio (`Agent/Inbox_Agent` o `Agent/Reports_Agent`) |
| `run_id` | frontmatter `run_id` |
| `capture_status` | frontmatter `capture_status` |
| `created_at_utc` | frontmatter `created_at_utc` |
| `updated_at_utc` | frontmatter `updated_at_utc` |
| `title` | frontmatter `capture_title` → primer `# heading` → stem del filename |
| `excerpt` | primeros 200 chars del cuerpo (sin headings ni énfasis) |

**El cuerpo completo de las notas nunca se expone ni se vuelca al audit log.**

## Tests añadidos

```
tests/restricted_operator/test_phase5_vault_read_chat.py
```

36 tests en 4 clases:
- `TestVaultReadChatListLastN` (6 tests)
- `TestVaultReadChatSearch` (7 tests)
- `TestVaultReadChatSummaryToday` (3 tests)
- `TestPhase5IntentDetection` (10 tests)
- `TestPhase5TelegramHandlers` (10 tests)

Suite completa: **131 tests OK**.

## Comandos de validación

### Compilación

```bash
python3 -m py_compile scripts/agents/openclaw/vault_read_chat.py
python3 -m py_compile scripts/agents/openclaw/restricted_operator/telegram_bot.py
python3 -m py_compile scripts/agents/openclaw/restricted_operator/assistant_responses.py
```

### Tests

```bash
cd /opt/control-plane

# Solo Phase 5:
python3 -m unittest tests.restricted_operator.test_phase5_vault_read_chat -v
# Esperado: 36 tests OK

# Suite completa:
python3 -m unittest \
  tests.restricted_operator.test_draft_promote_action \
  tests.restricted_operator.test_report_promote_action \
  tests.restricted_operator.test_phase4_obsidian_conversational \
  tests.restricted_operator.test_phase5_vault_read_chat
# Esperado: 131 tests OK
```

### Smoke test del lector

```bash
python3 -c "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, 'scripts/agents/openclaw')
from vault_read_chat import list_last_n, search_notes, summarize_today

with tempfile.TemporaryDirectory() as tmp:
    inbox = Path(tmp) / 'Agent' / 'Inbox_Agent'
    inbox.mkdir(parents=True)
    (inbox / '20260414T100000Z_inbox_demo.md').write_text(
        '---\nrun_id: \"demo\"\ncapture_status: \"pending_triage\"\n'
        'capture_title: \"Demo Phase 5\"\ncreated_at_utc: \"2026-04-14T10:00:00Z\"\n---\n'
        '# Demo Phase 5\n\n## Captura\n\nTexto de ejemplo con palabra verity.\n',
        encoding='utf-8')
    notes = list_last_n(tmp, 3)
    print('list_last_n:', len(notes), notes[0].title)
    found = search_notes(tmp, 'verity')
    print('search verity:', len(found), found[0].note_name)
    print('OK')
"
```

### Test end-to-end (Telegram)

```
# Últimas notas:
muéstrame las últimas 5 notas
→ Lista de notas más recientes con nombre, estado y título.

# Buscar:
busca verity
→ Resultados para 'verity': ...  (o "No encontré notas con 'verity'")

# Resumen hoy:
resúmeme lo guardado hoy
→ Guardado hoy 2026-04-14 — N nota(s): ...
```

## Riesgos abiertos

| Ref | Riesgo | Severidad |
|-----|--------|-----------|
| R5-1 | `Agent/Reports_Agent/` puede contener notas con formato diferente al de inbox; se leen igualmente, con degradación elegante si faltan campos de frontmatter | Baja |
| R5-2 | Búsqueda lineal O(N) — si el vault crece a miles de notas, el tiempo de respuesta aumenta. Aceptable para vault personal de un operador | Muy baja |
| R5-3 | `summarize_today` filtra por prefijo UTC del filename; si el bot corre en TZ local diferente a UTC, las notas del día pueden quedar desplazadas | Muy baja |
| R5-4 | El excerpt se trunca a 200 chars de texto plano. Si el cuerpo comienza con encabezados o metadatos, el excerpt puede ser poco representativo | Muy baja |

## Qué NO implementa esta fase

- Lectura del cuerpo completo de notas.
- Búsqueda semántica, embeddings o fuzzy matching.
- Filtrado por `capture_status` en `list_last_n` (se listan notas de cualquier estado).
- Paginación de resultados.
- Edición de cualquier nota.
- Lectura de directorios fuera de `Agent/Inbox_Agent` y `Agent/Reports_Agent`.
- Indexado persistente del vault.
- Cualquier mutación.

---

**Creado:** 2026-04-14
**Estado:** Phase 5 cerrada — 3 operaciones de lectura, 36 tests, 131 tests en suite completa
