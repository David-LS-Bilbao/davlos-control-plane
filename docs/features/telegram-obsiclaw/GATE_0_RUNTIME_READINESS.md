# Telegram OpenClaw Agente Operativo - GATE 0 Runtime Readiness
**Informe de auditoría operativa previa** | 2026-04-13

## Resumen Ejecutivo

El runtime actual de `davlos-control-plane` contiene una **baseline prudente validada** con piezas reutilizables completas para soportar los tres flujos mínimos de feature MVP sin romper el boundary existente. No hay blockers técnicos inmediatos, pero hay 4 gaps concretos entre el estado actual y el MVP operativo.

- **Estado de partida:** Telegram runtime operativo + broker restringido + policy viva con TTL + confirmación explícita + auditoría completa.
- **Piezas reutilizables encontradas:** 5/5 de lo mínimo necesario está implementado.
- **Gaps detectados:** Faltan 3 acciones específicas para inbox/draft/report y falta persistencia de estado de promoción.
- **Riesgos inmediatos:** Ninguno bloqueante; un riesgo residual de inference-gateway ya aparentemente corregido.
- **Recomendación:** **GO CON CONDICIONES** — proceder a MVP si se ejecutan los 3 cambios imprescindibles en orden mínimo.

---

## 1. Piezas Reutilizables Encontradas

### 1.1 Telegram Runtime (OPERATIVO)

**Fuente de verdad:**
- `/opt/control-plane/docs/TELEGRAM_OPENCLAW_RUNTIME_MVP.md` ✓
- `/opt/control-plane/scripts/agents/openclaw/restricted_operator/run_telegram_bot.sh` ✓
- `/opt/control-plane/scripts/agents/openclaw/restricted_operator/telegram_bot.py` ✓

**Estado:**
- Arrange/start/stop documentado y funcionando
- Rate limiting implementado (30s window, 6 requests)
- Polling largo contra Telegram validado
- Token fuera del repo ✓
- Auditoría de eventos de canal ✓

**Reutilización directa:**
- El flujo de Telegram ya valida `chat_id`/`user_id` -> `operator_id`
- Comando `/execute` ya existe y valida contra policy
- Callbacks de confirmación (`/yes`, `/no`, conversacional) ya funcionan
- Auditoría de `confirmation_requested`, `confirmation_accepted`, `confirmation_rejected` ya activa

### 1.2 Confirmación Explícita con Preview (OPERATIVO)

**Fuente de verdad:**
- `scripts/agents/openclaw/restricted_operator/telegram_bot.py` líneas 37-46 (PendingConfirmation)
- Líneas 596-628 (flujo de confirmation con summary)

**Estado:**
- Estructura `PendingConfirmation` almacena: `intent`, `operator_id`, `summary` (preview), `mutation`, `action_id`, `params`, `reason`
- Operador recibe `summary` antes de ejecutar (línea 625)
- Operador puede responder 'si' o 'no' (conversacional o comando)
- Confirmación rechazada cancela sin efecto (línea 368)
- Todo auditado (evento `confirmation_accepted`/`confirmation_rejected`)

**Reutilización directa:**
- Ya existe el patrón; se heredaría para intentos inbox/draft/report
- El campo `mutation` diferencia ya entre mutaciones (`set_enabled`, `enable_with_ttl`, `reset_one_shot`)
- Se requiere añadir `mutation` para promote operaciones

### 1.3 TTL y One-Shot (OPERATIVO)

**Fuente de verdad:**
- `/opt/control-plane/docs/BROKER_POLICY_TTL_MVP.md` ✓
- `scripts/agents/openclaw/restricted_operator/policy.py`

**Estado:**
- Expiración de acciones por `expires_at` ya evaluada en runtime
- One-shot consumible y resetteable vía CLI
- Estado efectivo combinado (declarado + runtime overrides) funcional
- Auditoría de `action_consumed_one_shot` activa

**Reutilización:**
- Ciclo inbox (si aplica TTL): set `enabled=true`, `expires_at=<future>`, operación concluida o expirada
- Potencial para "draft redactable durante 30 minutos, luego congelado"

### 1.4 Helper Readonly (OPERATIVO)

**Fuente de verdad:**
- `/opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh` ✓

**Estado:**
- 5 modos: `runtime_summary`, `broker_state_console`, `broker_audit_recent`, `telegram_runtime_status`, `operational_logs_recent`
- Requiere root pero no toca secretos ni archivos de producción
- Policy fallback si runtime no accesible
- Redaction automática de tokens/secrets

**Reutilización:**
- Modo `broker_audit_recent` ya da visibilidad de todos los eventos de confirmación/ejecución
- Se pueden añadir nuevos modos para `inbox_status`, `draft_status`, etc., sin cambiar el helper base

### 1.5 Broker Restringido y Auditoría (OPERATIVO)

**Fuente de verdad:**
- `/opt/control-plane/docs/BROKER_RESTRICTED_OPERATOR_MVP.md` ✓
- `/opt/control-plane/scripts/agents/openclaw/restricted_operator/broker.py`
- `/opt/control-plane/scripts/agents/openclaw/restricted_operator/audit.py`

**Acciones existentes:**
- `action.health.general.v1` (readonly)
- `action.logs.read.v1` (readonly)
- `action.webhook.trigger.v1` (restricted, no habilitada de base)
- `action.openclaw.restart.v1` (stub seguro, no habilitada)
- `action.dropzone.write.v1` (restricted, genérica)

**Estado:**
- Auditoría JSONL con campos: `ts`, `actor`, `action_id`, `ok`, `result`/`error`, `code`
- Ruta: `/opt/automation/agents/openclaw/broker/audit/restricted_operator.jsonl`
- Eventos auditados incluyen parámetros saneados sin exponer tokens

**Reutilización:**
- Acción `dropzone.write.v1` ya existe; **requiere refinamiento** para no permitir sobrescribir inbox/draft/report de operador ajeno
- Auditoría base lista; se heredaría para nuevas acciones

---

## 2. Gaps Concretos

### Gap 1: Falta acción específica para `inbox.write.v1`

**Descripción:**
- Existe `action.dropzone.write.v1` genérica, pero sin validación de propietario o namespace.
- Flujo MVP requiere que un operador escriba en su propio inbox sin poder tocar el de otro.

**Solución mínima:**
- Nueva acción `action.inbox.write.v1` que valide `operator_id` en parámetros
- Parámetro: `content` (payload de intención, validar tamaño)
- Ruta única: `/opt/automation/agents/openclaw/inbox/{operator_id}/{timestamp}.jsonl`
- Auditar: operador, timestamp, intent hash

**Esfuerzo:** Pequeño ajuste. 40-60 líneas de código Python.

### Gap 2: Falta acción `draft.promote.v1`

**Descripción:**
- No existe flujo de promoción inbox -> draft.
- Requiere: validar que entry existe en inbox, mover a draft, auditar transición.

**Solución mínima:**
- Nueva acción `action.draft.promote.v1`
- Parámetro: `inbox_id` (el timestamp/uuid de la entrada en inbox)
- Validación: el operador que pide promoción es dueño de la entrada
- Operación: leer inbox/{operator_id}/{inbox_id}, escribir draft/{operator_id}/{inbox_id}, auditar promoción
- TTL opcionale: `expires_at` en metadata si aplica (30 min para redactar)

**Esfuerzo:** Pequeño ajuste. 50-70 líneas.

### Gap 3: Falta acción `report.promote.v1`

**Descripción:**
- No existe flujo de promoción draft -> report.
- Requiere: validar entrada en draft, mover a report, auditar.

**Solución mínima:**
- Nueva acción `action.report.promote.v1`
- Parámetro: `draft_id` (timestamp/uuid de la entrada en draft)
- Validación: entrada existe, operador es dueño, draft no expirado
- Operación: leer draft/{operator_id}/{draft_id}, escribir report/{operator_id}/{draft_id}, auditar promoción

**Esfuerzo:** Pequeño ajuste. 50-70 líneas.

### Gap 4: Falta validación de ciclo de vida

**Descripción:**
- Policy no valida que solo puedas reportar si está en draft; ni que solo puedas redactar si está en inbox.

**Solución mínima:**
- Enum o flag en metadata: `state: "inbox" | "draft" | "report"`
- Validación en cada acción de promoción
- Rechazo explícito si state es incorrecto (ej: no puedes reportar si entrada nunca entró en draft)

**Esfuerzo:** Muy pequeño. 20-30 líneas de validación adicional.

---

## 3. Riesgos Inmediatos

### Riesgo: Exposición de inference-gateway (APARENTEMENTE RESUELTO)

**Hallazgo original:**
- En audit del 2026-04-01 se detectó que `inference-gateway` respondía en `0.0.0.0:11440`, no solo loopback.

**Estado actual según AGENTS.md (línea 21-22):**
```
- `inference-gateway` escucha solo en `127.0.0.1:11440` y `172.22.0.1:11440`
- `inference-gateway` ya no responde por la IP pública del host
```

**Validación:** No reabierto. ✓

**Acción:** Si durante MVP se inicia inference-gateway, validar bind con:
```bash
ss -lntp | grep 11440
```

---

## 4. Reutilización vs. Cambio

### Reutilización directa (sin cambios)

1. **Telegram runtime** → Heredar exactamente (run_telegram_bot.sh, bot polling, rate limiting)
2. **Confirmación explícita** → Patrón heredado; añadir nuevas `mutation` strings
3. **Helper readonly** → Sin cambios en hook base; agregar modos si aplica
4. **Auditoría JSONL** → Sin cambios; heredar para nuevas acciones

### Ajuste pequeño (< 100 líneas Python)

1. `action.inbox.write.v1` → Nueva clase en `actions.py`
2. `action.draft.promote.v1` → Nueva clase en `actions.py`
3. `action.report.promote.v1` → Nueva clase en `actions.py`
4. Validación de ciclo vida → Pequeño helper en `actions.py`

### Cambio nuevo imprescindible

1. **Directorio de inbox/draft/report** → Crear directorios bajo `/opt/automation/agents/openclaw/`:
   - `inbox/{operator_id}/`
   - `draft/{operator_id}/`
   - `report/{operator_id}/`
   - Validar permisos (755 parent, 750 per operator si multitenant)

2. **Integración en telegram_bot.py** → Detectar intención `inbox_write`, `draft_promote`, etc., y llamar broker correspondiente.

---

## 5. Secuencia Mínima Recomendada

### Fase A: Preparación (sin cambios en producción)

1. ✓ Leer baseline de Telegram runtime y confirmar operatividad
2. ✓ Leer baseline de broker restringido y confirmar auditoría
3. ✓ Confirmar que todos los directorios necesarios existen/pueden existir

### Fase B: Cambios de código mínimos (aislado, sin romper boundary)

1. **Crear 3 nuevas acciones en `actions.py`:**
   - `InboxWriteAction` (write validado por operator_id)
   - `DraftPromoteAction` (inbox -> draft con validación de state)
   - `ReportPromoteAction` (draft -> report con validación de state)

2. **Registrar acciones en policy template:**
   ```json
   "action.inbox.write.v1": { "enabled": true, "mode": "restricted", ... },
   "action.draft.promote.v1": { "enabled": true, "mode": "restricted", ... },
   "action.report.promote.v1": { "enabled": true, "mode": "restricted", ... }
   ```

3. **Extender telegram_bot.py:**
   - Añadir `mutation` strings: `"inbox_write"`, `"draft_promote"`, `"report_promote"`
   - Reutilizar flujo `_handle_conversation` -> pending confirmation -> `_execute_pending_confirmation`

### Fase C: Validación mínima

1. Test unitario en `tests/restricted_operator/test_broker.py` para cada acción
2. Test manual desde Telegram: enviar intención, confirmar, verificar auditoría
3. Validar directorios creados y permisos correctos

### Fase D: Hardening residual (después de MVP inicial)

- Validación de tamaño de payload inbox/draft/report
- TTL automático si aplica (ej: draft expira a los 30 min si no se reporta)
- Limpieza de archivos huérfanos
- Integración con obsi-claw-AI_agent para lectura final

---

## 6. Archivos de Referencia Confirmados

### Documentación base
- `docs/TELEGRAM_OPENCLAW_RUNTIME_MVP.md` ✓
- `docs/BROKER_RESTRICTED_OPERATOR_MVP.md` ✓
- `docs/BROKER_POLICY_TTL_MVP.md` ✓
- `docs/OPENCLAW_OPERATOR_FLOWS_MVP.md` ✓
- `docs/AGENTS.md` ✓

### Código operativo
- `scripts/agents/openclaw/restricted_operator/telegram_bot.py` ✓
- `scripts/agents/openclaw/restricted_operator/actions.py` ✓
- `scripts/agents/openclaw/restricted_operator/broker.py` ✓
- `scripts/agents/openclaw/restricted_operator/audit.py` ✓
- `scripts/agents/openclaw/restricted_operator/policy.py` ✓
- `templates/openclaw/restricted_operator_policy.json` ✓

### Helper
- `templates/openclaw/davlos-openclaw-readonly.sh` ✓
- `scripts/console/davlos-vpn-console.sh` ✓

### Tests
- `tests/restricted_operator/test_broker.py` ✓

### Reports recientes
- `docs/reports/OPENCLAW_BASELINE_RUNTIME_VALIDATION_2026-04-01.md` ✓
- `docs/reports/OPENCLAW_PHASE_2_BROKER_MVP_2026-04-01.md` ✓
- `docs/reports/OPENCLAW_PHASE_3_POLICY_TTL_MVP_2026-04-01.md` ✓
- `docs/reports/OPENCLAW_PHASE_4_CONSOLE_CAPABILITIES_2026-04-01.md` ✓

---

## 7. Recomendación Final

### Decisión: **GO CON CONDICIONES**

✓ **Condición 1:** Implementar las 3 acciones nuevas (`inbox.write.v1`, `draft.promote.v1`, `report.promote.v1`) con validación de state.

✓ **Condición 2:** Crear directorios de estado bajo `/opt/automation/agents/openclaw/inbox`, `draft`, `report` con permisos 750.

✓ **Condición 3:** Extender `telegram_bot.py` para reconocer intenciones de `inbox_write` y promoción, reutilizando el flujo de confirmación existente.

✓ **Condición 4:** Validar en tests unitarios que el ciclo inbox -> draft -> report rechaza transiciones no permitidas.

✗ **No es bloqueante:**
- Helper readonly (ya existe)
- Auditoría (ya existe)
- TTL (ya existe)
- Confirmación explícita (ya existe)
- Telegram runtime (ya existe)

### Motivo

El boundary operativo actual está **suficientemente validado** para soportar el MVP sin ruptura. Las piezas mínimas de Telegram, broker, policy viva y auditoría están en su lugar. Los gaps son únicamente **aciones nuevas muy pequeñas** que reutilizan patrones ya validados. El riesgo residual de inference-gateway aparentemente ya fue resuelto según documentación reciente.

---

## 8. Siguiente Paso Mínimo Recomendado

**Inmediato (antes de Phase 1):**

1. Crear rama de trabajo: `feat/telegram-obsiclaw-inbox-draft-report`
2. Implementar las 3 acciones en `actions.py` (estimado: 2-4 horas)
3. Actualizar policy template con las 3 acciones
4. Extender `telegram_bot.py` con detection de intención + confirmación
5. Crear tests unitarios (estimado: 1-2 horas)
6. Validar directorios de estado existen
7. Ejecutar end-to-end local: enviar mensaje Telegram → inbox → confirm → draft → confirm → report
8. Auditar flujo: `bash /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh broker_audit_recent`
9. Merge a `main` si auditoría es limpia

**No partir de cero. Reutilizar patterns validados. Cambios mínimos y auditables.**

---

## 9. Notas Operativas

- El repo `/opt/control-plane` es la fuente de verdad operativa correcta.
- El repo `obsi-claw-AI_agent` define el contrato de entrada (donde escribe `inbox`).
- No es necesario sincronizar ambos en esta fase; boundary es claro.
- Drift operativo en UFW existe pero no bloquea MVP; normalizarse en hardening posterior.
- No modificar `systemd`, `sudoers`, secretos ni runtime host-side en esta fase.

---

**Creado:** 2026-04-13  
**Rama:** feat/obsi-claw-agent-operativo-gate-0  
**Auditor:** Senior Software Engineer + Security-conscious Operator
