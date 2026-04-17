# Phase 9 — Sandbox Mode + E5/E6

**Estado:** Completa — rama `feat/phase8-vault-crud` (pendiente merge)

## Objetivo

Activar un modo conversacional libre donde un LLM local (`qwen2.5:3b` vía Ollama) tiene acceso completo al vault en tiempo real, puede ejecutar acciones directamente, y el usuario puede interactuar de forma natural sin restricción de intents predefinidos.

---

## Funcionalidades implementadas

### Sandbox mode

| Trigger de activación | Trigger de desactivación |
|---|---|
| `activa modo libre` | `sal del sandbox` |
| `libera openclaw` | `modo normal` |
| `sandbox on` | `sandbox off` |

- Estado por chat (`_sandbox_mode: dict[str, bool]`)
- Se limpia en `/sleep` o restart del servicio
- En sandbox: el mensaje va directamente a `SandboxLLMAgent`

### Contexto vault dinámico

Por cada mensaje en sandbox, el sistema construye un bloque de contexto que incluye:
1. Lista de todas las secciones con sus notas (hasta 12 por sección)
2. Keywords extraídas del mensaje del usuario (máx. 4, sin stopwords)
3. Notas relevantes encontradas vía `search_vault_broad` con extracto

El LLM recibe este contexto en el system prompt, dándole visibilidad real y actualizada del vault.

### Acciones LLM en sandbox

El LLM puede emitir acciones usando la sintaxis:
```
<action>{"action_id": "action.note.create.v1", "params": {...}}</action>
```

Las acciones se ejecutan directamente via broker (sin confirmación adicional del usuario). El resultado se devuelve al LLM como contexto para su respuesta final.

Acciones disponibles desde sandbox: `action.note.create.v1`, `action.note.archive.v1`, `action.note.edit.v1`, `action.note.move.v1`

### E5 — Editar nota

Frases: `añade a <nota>: <texto>`, `edita <nota>: <nuevo contenido>`

- Acción: `action.note.edit.v1`
- Modos: `append` (añadir al final) o `replace` (reemplazar contenido)
- Fuera de sandbox: requiere confirmación explícita
- En sandbox: el LLM puede ejecutarlo directamente

### E6 — Mover nota

Frases: `mueve <nota> a <carpeta>`, `mueve <nota> a la carpeta <carpeta>`

- Acción: `action.note.move.v1`
- Fuzzy-resolve de carpeta destino
- Maneja colisiones con sufijo de timestamp
- Fuera de sandbox: requiere confirmación explícita
- En sandbox: el LLM puede ejecutarlo directamente

---

## Módulos nuevos

### `llm_agent.py` — `SandboxLLMAgent`

- Historial de conversación por sesión (`deque`, máx. configurable)
- Llamada a Ollama API (`http://127.0.0.1:11440/v1/chat/completions`)
- `_parse_action(text)` → extrae JSON de tags `<action>...</action>`
- `_extract_text(response)` → parsea respuesta OpenAI-compatible
- El historial se recorta DESPUÉS de añadir tanto el mensaje del usuario como la respuesta del asistente

---

## Seguridad en E5/E6

- Las rutas se validan con `Path.resolve()` dentro de `vault_root`
- Las carpetas `Agent`, `.obsidian`, `.git` están bloqueadas como origen y destino
- Path traversal rechazado con código `invalid_params`
- Todas las acciones pasan por broker con auditoría, incluso desde sandbox

---

## Detalle técnico: normalización de texto

El matcher de E5/E6 usa `original_text.lower()` (no el texto normalizado) para preservar:
- El separador `:` en `añade a nota: texto`
- El punto en nombres de archivo como `demo.md`

`find_note_anywhere` trata la consulta como stem (sin extensión) antes de normalizar.

---

## Archivos modificados / creados

| Archivo | Cambio |
|---|---|
| `scripts/agents/openclaw/llm_agent.py` | **NUEVO** — `SandboxLLMAgent` |
| `scripts/agents/openclaw/vault_browser.py` | `search_vault_broad`, `_first_excerpt`, filtro pipeline artifacts, fix `find_note_anywhere` |
| `restricted_operator/telegram_bot.py` | Sandbox mode, `_handle_sandbox_message`, `_build_sandbox_vault_context`, intents E5/E6 |
| `restricted_operator/actions.py` | `NoteEditAction`, `NoteMoveFolderAction` + registro |
| `restricted_operator/assistant_responses.py` | Renders sandbox + E5/E6 |
| `templates/openclaw/restricted_operator_policy.json` | Sección `sandbox_mode`, entradas E5/E6 |
| `tests/restricted_operator/test_phase9_sandbox_mode.py` | **NUEVO** — 33 tests |
| `tests/restricted_operator/test_phase9_note_edit_move.py` | **NUEVO** — 24 tests |

---

## Tests

```bash
python3 -m unittest tests/restricted_operator/test_phase9_sandbox_mode.py -v
python3 -m unittest tests/restricted_operator/test_phase9_note_edit_move.py -v
```

Suite completa:
```bash
python3 -m unittest discover -s tests/restricted_operator -p "test_*.py" 2>&1 | tail -3
# Ran 381 tests in ...s  OK
```

---

## Pendiente para producción

1. Añadir en policy live (`/opt/automation/agents/openclaw/broker/restricted_operator_policy.json`):
   - `action.note.edit.v1` con `enabled: true`
   - `action.note.move.v1` con `enabled: true`
2. Restart del servicio: `sudo systemctl restart openclaw-telegram-bot.service`
3. Merge del PR `feat/phase8-vault-crud` en GitHub
