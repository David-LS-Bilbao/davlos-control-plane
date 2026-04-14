# Obsi-Claw MVP Operativo — Documento de Supervisión
**Fecha:** 2026-04-14 | **Estado:** MVP cerrado, listo para supervisión

---

## 1. Alcance exacto del MVP operativo

Obsi-Claw es un agente Telegram controlado que permite a un operador autorizado capturar notas y promoverlas a través de un ciclo de vida estructurado en su vault de Obsidian, con confirmación explícita antes de cada mutación y auditoría completa de cada evento.

**Perímetro operativo activo:**

- Un operador autorizado por chat_id y policy envía comandos o frases naturales desde Telegram.
- El bot valida permisos, muestra un resumen de la acción y espera confirmación (`si`/`no`).
- Tras confirmación, ejecuta la acción a través del broker restringido y registra el resultado en auditoría JSONL.
- El vault de Obsidian recibe evidencia en forma de archivos create-only o actualizaciones de `capture_status`.
- Ninguna acción modifica el vault sin confirmación explícita del operador.

**Lo que no entra en el perímetro:** shell libre, lectura arbitraria del vault, edición de notas existentes, automatización autónoma sin confirmación.

---

## 2. Workflows validados en runtime

### Workflow 1 — `inbox.write`

```
Operador → Telegram → confirmación → nota create-only en Agent/Inbox_Agent/
```

- Crea un archivo `{timestamp}_inbox_{run_id}.md` con `capture_status: "pending_triage"`.
- No sobreescribe. Si el archivo ya existe, falla con error explícito.
- Auditado: `confirmation_requested` → `confirmation_accepted` → `action_executed`.

### Workflow 2 — `draft.promote`

```
Operador → Telegram → confirmación → STAGED_INPUT.md creado + nota marcada promoted_to_draft
```

- Solo actúa sobre notas con `capture_status: "pending_triage"`.
- Crea `STAGED_INPUT.md` en `Agent/Inbox_Agent/` para el pipeline de draft.
- Si `STAGED_INPUT.md` ya existe, falla con `staging_conflict`.
- Auditado ídem.

### Workflow 3 — `report.promote`

```
Operador → Telegram → confirmación → REPORT_INPUT.md creado + nota marcada promoted_to_report
```

- Solo actúa sobre notas con `capture_status: "promoted_to_draft"`.
- Crea `REPORT_INPUT.md` en `Agent/Inbox_Agent/` para el pipeline de report.
- Si `REPORT_INPUT.md` ya existe, falla con `report_conflict`.
- Auditado ídem.

### Ciclo de vida validado

```
[captura]         inbox.write      → pending_triage
[primer paso]     draft.promote    → promoted_to_draft   + STAGED_INPUT.md
[cierre]          report.promote   → promoted_to_report  + REPORT_INPUT.md
```

Transiciones en sentido contrario o salteadas son rechazadas por el broker. La policy controla qué operador puede ejecutar cada acción.

---

## 3. Ejemplos reales de uso

### Vía slash commands (siempre disponibles)

```
/inbox_write run_id=reunión-20260414 title=Plan+costes :: Revisar costes del Q2 con equipo financiero.

/draft_promote note=20260414T103045Z_inbox_reunión-20260414.md

/report_promote note=20260414T103045Z_inbox_reunión-20260414.md
```

### Vía lenguaje natural (Phase 4 — activo)

```
# Capturar
guarda esta idea: Plan de costes Q2 :: Revisar con el equipo financiero antes del jueves.

# Listar qué hay pendiente de triaje
qué tengo pendiente

# Promover la última nota a draft
promueve la ultima a draft

# Listar notas listas para report
listas para report

# Promover una nota específica a report
promueve la ultima a report

# Consultar el estado de una nota
estado de reunión-20260414
```

### Flujo completo desde Telegram (conversacional)

```
Operador:  guarda esta idea: Análisis Q2 :: Revisar márgenes antes del lunes.
Bot:       Acción interpretada:
           inbox.write | run_id=tg-20260414T103045 | title=Análisis Q2 | body=42 B
           Responde 'si' para ejecutar o 'no' para cancelar.

Operador:  si
Bot:       Captura guardada.
           nota: 20260414T103045Z_inbox_tg-20260414T103045.md

Operador:  promueve la ultima a draft
Bot:       Acción interpretada:
           draft.promote | note=20260414T103045Z_inbox_tg-20260414T103045.md (estado: pending_triage)
           Responde 'si' para ejecutar o 'no' para cancelar.

Operador:  si
Bot:       Nota promovida a draft.
           nota: 20260414T103045Z_inbox_tg-20260414T103045.md
           staging: STAGED_INPUT.md creado

Operador:  promueve la ultima a report
Bot:       Acción interpretada:
           report.promote | note=20260414T103045Z_inbox_tg-20260414T103045.md (estado: promoted_to_draft)
           Responde 'si' para ejecutar o 'no' para cancelar.

Operador:  si
Bot:       Nota promovida a report.
           nota: 20260414T103045Z_inbox_tg-20260414T103045.md
           report: REPORT_INPUT.md creado
```

---

## 4. Evidencias mínimas a enseñar en supervisión

### 4.1 Auditoría de eventos recientes

```bash
bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh broker_audit_recent
```

Muestra el JSONL de eventos. Buscar secuencia:
`confirmation_requested` → `confirmation_accepted` → `action_executed`

### 4.2 Estado del runtime

```bash
bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh telegram_runtime_status
```

Confirma que el bot está activo y cuándo procesó el último update.

### 4.3 Evidencia en vault (directo)

```bash
ls -lh /ruta/al/vault/Agent/Inbox_Agent/
# Notar archivos con patrón 20*_inbox_*.md
# Notar STAGED_INPUT.md si hay un draft en curso
# Notar REPORT_INPUT.md si hay un report en curso

grep capture_status /ruta/al/vault/Agent/Inbox_Agent/20*.md
```

### 4.4 Compilación limpia + tests

```bash
cd /opt/control-plane

python3 -m py_compile scripts/agents/openclaw/restricted_operator/telegram_bot.py && echo "OK"
python3 -m py_compile scripts/agents/openclaw/restricted_operator/actions.py && echo "OK"

python3 -m unittest \
  tests.restricted_operator.test_draft_promote_action \
  tests.restricted_operator.test_report_promote_action \
  tests.restricted_operator.test_phase4_obsidian_conversational
# Esperado: 95 tests OK
```

### 4.5 Policy activa

```bash
python3 /opt/control-plane/scripts/agents/openclaw/restricted_operator/cli.py \
  --policy /opt/automation/agents/openclaw/broker/restricted_operator_policy.json \
  list
```

Muestra qué acciones están habilitadas y con qué permisos.

---

## 5. Riesgos y deuda abiertos

| Ref | Riesgo / Deuda | Severidad | Impacto |
|-----|---------------|-----------|---------|
| R-1 | `STAGED_INPUT.md` y `REPORT_INPUT.md` no los consume el broker — depende del pipeline de Obsidian | Baja | Si el pipeline no procesa, los archivos se acumulan; la siguiente promoción falla con conflict |
| R-2 | Reconocimiento conversacional basado en frases exactas — frases no previstas no se detectan | Baja | Usuario recibe `render_conversation_help()` con ejemplos; slash commands siempre funcionan |
| R-3 | Token search alfanumérico puede generar falsos positivos con run_ids muy cortos | Muy baja | No afecta en producción con run_ids descriptivos; usuario confirma antes de ejecutar |
| R-4 | Ownership de notas no validado a nivel de archivo (sistema es single-operator hoy) | Baja | No aplica hasta escenario multitenant |
| R-5 | `vault_root` apunta a ruta absoluta en policy; si el vault cambia de ruta, requiere actualización manual | Baja | Operación de mantenimiento conocida |

---

## 6. Qué NO hace todavía el sistema

- **No lee el contenido** de notas existentes (solo lee `capture_status` y `run_id` de frontmatter).
- **No edita** notas existentes (solo actualiza `capture_status` como parte del ciclo controlado).
- **No borra** nada en el vault.
- **No actúa de forma autónoma**: toda mutación requiere confirmación explícita del operador.
- **No hace búsqueda semántica** ni interpreta el cuerpo de las notas.
- **No publica** el contenido de las notas a ningún servicio externo.
- **No arranca ni detiene** el pipeline de Obsidian (`obsi-claw-AI_agent`).
- **No gestiona múltiples operadores** con namespaces separados en el vault.
- **No tiene TTL automático** en drafts no promovidos (deuda documentada, no implementada).

---

## 7. Checklist de demo de 5 minutos

Ejecutar en este orden desde Telegram con el bot activo:

```
[ ] 1. Verificar que el bot responde:
        /status
        → Debe mostrar operator=davlos-operator, acciones activas.

[ ] 2. Listar notas pendientes (lectura):
        qué tengo pendiente
        → Lista vacía o notas existentes. Sin mutación.

[ ] 3. Capturar una nota nueva:
        guarda esta idea: Demo supervisión :: Nota de prueba para demo operativa.
        → Bot muestra preview con run_id generado.
        si
        → "Captura guardada." + nombre del archivo.

[ ] 4. Verificar nota en vault:
        (auditor) ls Agent/Inbox_Agent/ | grep tg-
        (auditor) grep capture_status Agent/Inbox_Agent/20*tg*.md
        → capture_status: "pending_triage"

[ ] 5. Promover a draft:
        promueve la ultima a draft
        → Bot muestra nota concreta a promover.
        si
        → "Nota promovida a draft." + STAGED_INPUT.md creado.

[ ] 6. Verificar evidencia:
        (auditor) ls Agent/Inbox_Agent/STAGED_INPUT.md
        (auditor) grep capture_status Agent/Inbox_Agent/20*tg*.md
        → capture_status: "promoted_to_draft"

[ ] 7. Promover a report:
        promueve la ultima a report
        si
        → "Nota promovida a report." + REPORT_INPUT.md creado.

[ ] 8. Verificar auditoría completa:
        bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh broker_audit_recent
        → Ver secuencia de 3 pares confirmation_requested / action_executed.

[ ] 9. Probar rechazo de doble promoción:
        promueve la ultima a draft
        si
        → Error: "staging_conflict" o "not_promotable". No hay efecto en vault.
```

**Criterio de éxito:** pasos 1-8 completados sin errores. El paso 9 confirma que el sistema rechaza operaciones inválidas.

---

**Creado:** 2026-04-14
**Scope:** MVP operativo cerrado — 4 phases implementadas, 95 tests, 3 workflows en producción
