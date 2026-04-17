# Phase 8 — Vault CRUD (E1-E4)

**Estado:** Completa — rama `feat/phase8-vault-crud` (pendiente merge)

## Objetivo

Añadir capacidad de lectura conversacional completa del vault y operaciones de escritura controladas (crear y archivar notas) desde Telegram, pasando siempre por el broker con auditoría.

---

## Funcionalidades implementadas

### E1 — Leer nota

Frases: `que dice <nota>`, `léeme <nota>`, `muéstrame <nota>`, `contenido de <nota>`

- Busca la nota en todo el vault (`find_note_anywhere`)
- Muestra hasta 60 líneas; indica truncado si hay más
- Si hay múltiples coincidencias, lista candidatos y pide más precisión

### E2 — Explorar secciones

Frases: `qué carpetas hay`, `qué secciones tiene el vault`, `qué hay en <carpeta>`

- `list_vault_sections` → lista directorios top-level con conteo de notas
- `list_notes_in_section` → lista notas dentro de una carpeta concreta
- Fuzzy-resolve de nombres de carpeta (`resolve_vault_section`)

### E3 — Crear nota

Frase: `crea una nota en <carpeta>: <título> :: <cuerpo>`

- Acción: `action.note.create.v1`
- Nombre de archivo generado: `YYYYMMDDTHHMMSSZ_inbox_<slug>.md`
- Requiere confirmación antes de ejecutar
- Bloqueado en carpetas reservadas (`Agent`, `.obsidian`, `.git`)

### E4 — Archivar nota

Frase: `archiva <nota>`, `mueve al archivo <nota>`

- Acción: `action.note.archive.v1`
- Mueve la nota a la sección `50_Archivado` (o equivalente fuzzy-resuelto)
- Maneja colisiones con sufijo de timestamp
- Requiere confirmación antes de ejecutar

---

## Módulos nuevos

### `vault_browser.py`

Lectura y exploración del vault (read-only):
- `list_vault_sections(vault_root)` → `list[VaultSection]`
- `list_notes_in_section(vault_root, folder_rel)` → `list[str]`
- `find_note_anywhere(vault_root, note_ref)` → `list[tuple[str, Path]]`
- `read_note_content(vault_root, note_rel_path)` → `NoteContent | None`
- `search_vault_broad(vault_root, query)` → `list[tuple[str, str]]`
- `resolve_vault_section(vault_root, folder_ref)` → `str | None`

Excluye: directorios `Agent`, `.obsidian`, `.git` y pipeline artifacts (`STAGED_INPUT.md`, `REPORT_INPUT.md`).

---

## Seguridad

- Todas las rutas se resuelven con `Path.resolve()` y se verifica que queden dentro de `vault_root`
- Las carpetas reservadas están bloqueadas en las acciones (código `forbidden`)
- Path traversal (`../etc/passwd`) rechazado con código `invalid_params`

---

## Archivos modificados / creados

| Archivo | Cambio |
|---|---|
| `scripts/agents/openclaw/vault_browser.py` | **NUEVO** — navegación read-only del vault |
| `restricted_operator/actions.py` | `NoteCreateAction`, `NoteArchiveAction` + registro |
| `restricted_operator/telegram_bot.py` | Intents E1-E4, handlers, imports |
| `restricted_operator/assistant_responses.py` | Renders E1-E4 |
| `templates/openclaw/restricted_operator_policy.json` | Entradas para `action.note.create.v1`, `action.note.archive.v1` |
| `tests/restricted_operator/test_phase8_vault_crud.py` | Tests de la fase |

---

## Tests

```bash
python3 -m unittest tests/restricted_operator/test_phase8_vault_crud.py -v
```
