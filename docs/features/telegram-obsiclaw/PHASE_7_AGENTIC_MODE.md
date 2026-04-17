# Phase 7 — Modo Agentico (A/B/C/D)

**Estado:** Completa — mergeada en `main`

## Objetivo

Transformar el bot de canal corto de comandos a asistente conversacional con estado de sesión, confirmaciones explícitas para mutaciones, y soporte de fallback LLM ampliado.

---

## Funcionalidades implementadas

### A — Wake persistente con operador activo

- `despertar` / `wake` / `hola openclaw` → activa sesión de asistente con operador reconocido
- `dormir` / `sleep` / `hasta luego` → cierra sesión y limpia estado pendiente
- El asistente mantiene estado `active/sleeping` por chat
- Sin `wake`, el bot opera en modo restringido (solo comandos directos)

### B — Confirmaciones para mutaciones

Todas las acciones mutantes (E3 crear nota, E4 archivar) requieren confirmación explícita:
- Bot presenta resumen de la acción pendiente con `¿Confirmas? (sí/no)`
- `sí` / `si` → ejecuta
- `no` / `cancel` → descarta
- Cualquier otro mensaje con sesión activa → descarta pendiente y procesa como nuevo intent

### C — Intents conversacionales ampliados

| Frase | Intent |
|---|---|
| `qué puedes hacer` | `obsidian.help` |
| `ayuda` | `obsidian.help` |
| `estado de <nota>` | `obsidian.note_status` |
| `hay artefactos pendientes` | `obsidian.pending_artifacts` |
| `qué bloquea <nota>` | `obsidian.what_blocks` |

### D — Fallback LLM en modo wake

Cuando el matcher local no resuelve un mensaje y el asistente está en wake, enruta a LLM local (`qwen2.5:3b` vía Ollama). El LLM no ejecuta acciones — solo responde conversacionalmente.

---

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `restricted_operator/telegram_bot.py` | Wake/sleep handlers, `_pending_confirmation` dict, fallback LLM routing |
| `restricted_operator/assistant_responses.py` | Renders de wake, sleep, confirmación, cancelación |
| `restricted_operator/actions.py` | Refactor para retorno uniforme `ActionResult` |
| `tests/restricted_operator/test_phase7_agentic_mode.py` | Tests de la fase |

---

## Tests

```bash
python3 -m unittest tests/restricted_operator/test_phase7_agentic_mode.py -v
```
