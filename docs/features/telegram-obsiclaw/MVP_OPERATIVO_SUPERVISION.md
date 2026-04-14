# Obsi-Claw — MVP Operativo: Documento de Supervisión
**Fecha:** 2026-04-14 | **Rama:** `feat/obsi-claw-agent-operativo-gate-0`

---

## 1. Estado actual del MVP

Obsi-Claw es un agente Telegram operativo que permite capturar, promover y consultar notas de Obsidian desde el móvil con confirmación explícita antes de cada mutación y auditoría completa de cada evento.

**5 phases cerradas. 131 tests OK. Sin APIs externas ni LLM en producción.**

---

## 2. Capacidades ya operativas

| Capacidad | Acción | Estado |
|-----------|--------|--------|
| Captura de notas | `action.inbox.write.v1` | Operativa |
| Promoción a draft | `action.draft.promote.v1` | Operativa |
| Promoción a report | `action.report.promote.v1` | Operativa |
| Capa conversacional | 7 intents en lenguaje natural | Operativa |
| Lectura del vault | `list_last_n`, `search_text`, `summary_today` | Operativa |

El bot valida permisos, muestra un resumen de la acción propuesta y espera `si`/`no` antes de cualquier mutación. Las lecturas son inmediatas, sin confirmación.

---

## 3. Workflows validados en runtime

### Mutaciones (con confirmación explícita)

```
[captura]       inbox.write      → crea nota pending_triage en Agent/Inbox_Agent/
[primer paso]   draft.promote    → marca nota promoted_to_draft + crea STAGED_INPUT.md
[cierre]        report.promote   → marca nota promoted_to_report + crea REPORT_INPUT.md
```

Transiciones inversas o saltadas son rechazadas. La policy controla qué operador puede ejecutar cada acción.

### Lecturas (sin confirmación, respuesta inmediata)

```
list_last_n     → últimas N notas de Inbox_Agent + Reports_Agent
search_text     → búsqueda por substring en título y extracto
summary_today   → notas cuyo timestamp de filename coincide con hoy UTC
```

---

## 4. Qué se puede demostrar en 5 minutos

```
[ ] 1. Bot responde:
        /status
        → operator=davlos-operator, acciones activas.

[ ] 2. Capturar una nota:
        guarda esta idea: Demo :: Nota de prueba para supervisión.
        → Bot muestra preview con run_id generado.
        si
        → "Captura guardada." + nombre del archivo.

[ ] 3. Ver qué hay pendiente:
        qué tengo pendiente
        → Lista la nota recién creada (estado: pending_triage).

[ ] 4. Promover a draft:
        promueve la ultima a draft
        → Bot muestra la nota a promover.
        si
        → "Nota promovida a draft." + STAGED_INPUT.md creado.

[ ] 5. Promover a report:
        promueve la ultima a report
        si
        → "Nota promovida a report." + REPORT_INPUT.md creado.

[ ] 6. Buscar en el vault:
        busca demo
        → Aparece la nota recién creada con título y extracto.

[ ] 7. Ver auditoría:
        bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh broker_audit_recent
        → Secuencia confirmation_requested → confirmation_accepted → action_executed × 3.

[ ] 8. Probar rechazo:
        promueve la ultima a draft
        si
        → Error: staging_conflict o not_promotable. Sin efecto en vault.
```

**Criterio de éxito:** pasos 1-7 sin errores. El paso 8 confirma que el sistema rechaza operaciones inválidas.

---

## 5. Ejemplos reales de uso

### Slash commands

```
/inbox_write run_id=reunión-abril title=Costes+Q2 :: Revisar márgenes antes del lunes.

/draft_promote note=20260414T103045Z_inbox_reunión-abril.md

/report_promote note=20260414T103045Z_inbox_reunión-abril.md
```

### Frases conversacionales — mutaciones

```
guarda esta idea: Análisis Q2 :: Revisar márgenes antes del lunes.

promueve la ultima a draft

promueve la ultima a report
```

### Frases conversacionales — lecturas

```
qué tengo pendiente

busca análisis

muéstrame las últimas 5 notas

resúmeme lo guardado hoy

estado de reunión-abril
```

---

## 6. Evidencias mínimas

### Auditoría de eventos

```bash
bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh broker_audit_recent
```
Buscar secuencia: `confirmation_requested` → `confirmation_accepted` → `action_executed`.

### Estado del runtime

```bash
bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh telegram_runtime_status
```
Confirma que el bot está activo y el timestamp del último update procesado.

### Evidencia en vault

```bash
ls -lh /ruta/vault/Agent/Inbox_Agent/
grep capture_status /ruta/vault/Agent/Inbox_Agent/20*.md
# pending_triage → promoted_to_draft → promoted_to_report
```

### Tests

```bash
cd /opt/control-plane
python3 -m unittest \
  tests.restricted_operator.test_draft_promote_action \
  tests.restricted_operator.test_report_promote_action \
  tests.restricted_operator.test_phase4_obsidian_conversational \
  tests.restricted_operator.test_phase5_vault_read_chat
# Esperado: 131 tests OK
```

### Compilación limpia

```bash
python3 -m py_compile scripts/agents/openclaw/restricted_operator/telegram_bot.py && echo OK
python3 -m py_compile scripts/agents/openclaw/vault_read_chat.py && echo OK
```

---

## 7. Límites actuales

**El sistema no hace las siguientes cosas, de forma deliberada:**

- No lee el **cuerpo completo** de las notas (solo título y extracto de 200 chars).
- No edita notas existentes (solo actualiza `capture_status` como parte del ciclo controlado).
- No borra nada en el vault.
- No actúa de forma autónoma: toda mutación requiere confirmación explícita del operador.
- No hace búsqueda semántica ni por similitud — solo substring exacto en título/extracto.
- No gestiona múltiples operadores con namespaces separados (sistema single-operator).
- No arranca ni detiene el pipeline de Obsidian (`obsi-claw-AI_agent`).
- No publica contenido de notas a ningún servicio externo.
- No pagina resultados de búsqueda (máximo 8 resultados por búsqueda).
- No tiene TTL automático en drafts no promovidos.

---

## 8. Deuda técnica abierta

| Ref | Deuda | Severidad |
|-----|-------|-----------|
| D-1 | `STAGED_INPUT.md` y `REPORT_INPUT.md` no los consume el broker — depende del pipeline de Obsidian externo | Baja |
| D-2 | Reconocimiento conversacional basado en frases exactas — frases no previstas devuelven ayuda | Baja |
| D-3 | Búsqueda lineal O(N) sobre el vault — aceptable para vault personal, no para colecciones grandes | Muy baja |
| D-4 | `summarize_today` filtra por timestamp UTC del filename; notas creadas en TZ local pueden no aparecer | Muy baja |
| D-5 | `vault_root` apunta a ruta absoluta en policy; si el vault cambia de ruta requiere actualización manual | Baja |

---

## 9. Conclusión ejecutiva

Obsi-Claw es un agente Telegram de captura y consulta de notas Obsidian operativo, auditado y controlado: ninguna mutación ocurre sin confirmación explícita, ningún dato sale del sistema y el vault permanece como única fuente de verdad.

---

**Actualizado:** 2026-04-14
**Scope:** 5 phases, 131 tests, 3 workflows de mutación + 3 operaciones de lectura en producción
