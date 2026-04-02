# Telegram OpenClaw Assistant LLM Phase 16

Fecha: 2026-04-01
Rama objetivo: `codex/openclaw-console-readonly`
Estado: propuesta lista para implementación

## objetivo

Evolucionar el canal Telegram de OpenClaw desde un asistente conversacional cerrado por reglas hacia un asistente más natural, tipo GPT, sin romper el modelo de seguridad actual.

La meta no es crear un chatbot libre ni darle acceso general al VPS. La meta es mejorar:

- comprensión de lenguaje natural
- redacción de respuestas
- propuestas de acción

manteniendo:

- allowlist Telegram
- `operator_auth`
- policy viva
- broker restringido
- confirmación obligatoria para mutaciones
- auditoría completa

## decisión de arquitectura

La estrategia recomendada es:

- mantener el asistente cerrado actual como base determinista
- añadir un adapter LLM seguro y opcional solo para comprensión/redacción
- no crear todavía un segundo bot separado

En resumen:

- A sola tiene techo rápido
- B sobre A es la mejor evolución inmediata
- C se puede evaluar más adelante, no ahora

## principio de seguridad

El LLM no debe ejecutar nada directamente.

El LLM solo puede:

- interpretar intención
- proponer una acción cerrada
- redactar una respuesta natural
- resumir estado, auditoría o logs permitidos

El LLM no puede:

- ejecutar shell
- construir comandos Bash
- leer el filesystem libremente
- hablar con Docker o systemd
- mutar policy por su cuenta
- saltarse confirmación

## arquitectura propuesta

```text
Telegram
  -> Telegram Bot Adapter
    -> Intent Router
      -> Rule Engine
      -> LLM Adapter (fallback controlado)
    -> Schema Validator
    -> Policy/Auth Guard
    -> Confirmation Manager
    -> Restricted Broker
    -> Audit Logger
```

## flujo operativo

1. Telegram recibe un mensaje.
2. El bot resuelve identidad por `chat_id/user_id -> operator_id`.
3. Si el mensaje es slash command o confirmación, se resuelve por reglas.
4. Si es conversación natural:
   - primero intenta matcher local
   - si no basta y la sesión está en `wake`, se llama al LLM
5. El LLM devuelve una salida estructurada cerrada.
6. El backend valida schema y campos permitidos.
7. El backend valida auth + policy.
8. Si es lectura, responde.
9. Si es mutación, propone acción y pide confirmación.
10. Solo tras confirmación se ejecuta por broker o mutación controlada.

## regla clave

El LLM nunca decide la ejecución real.

La ejecución real siempre sigue esta cadena:

`Telegram -> auth -> policy -> confirmation -> broker`

## cuándo invocar LLM

Sí:

- preguntas naturales ambiguas o abiertas
- explicación del estado
- reformulación de auditoría
- propuesta de acción
- frases tipo:
  - `quién eres`
  - `qué recomiendas`
  - `explícame qué está pasando`
  - `resume lo importante`

No:

- slash commands
- confirmaciones `si/no`
- parsing crítico de parámetros ya bien cubierto por reglas
- ejecución directa de mutaciones
- cualquier mensaje que ya encaje limpiamente en el modo cerrado

## contrato de salida del LLM

La salida del modelo debe ser JSON estructurado y validado. No texto libre para acciones.

Ejemplo:

```json
{
  "intent": "enable_capability_with_ttl",
  "action_id": "action.dropzone.write.v1",
  "params": {
    "ttl_minutes": 15
  },
  "needs_confirmation": true,
  "reply": "Puedo habilitar temporalmente esa capacidad durante 15 minutos."
}
```

## intents permitidos

Lectura:

- `status`
- `capabilities`
- `audit_tail`
- `logs_read`
- `explain_status`
- `suggest_action`
- `assistant_identity`

Mutación controlada:

- `enable_capability`
- `disable_capability`
- `enable_capability_with_ttl`
- `reset_one_shot`

Fallback:

- `unsupported`

## validaciones obligatorias

Antes de aceptar la salida del LLM:

- JSON válido
- schema válido
- `intent` dentro de allowlist
- `action_id` existente si aplica
- `params` permitidos y tipados
- longitud acotada
- sin campos extra peligrosos

Antes de ejecutar:

- operador allowlisted
- permiso del operador
- acción permitida por policy
- confirmación obligatoria si es mutación

## fallback seguro

Si el LLM:

- no responde
- responde fuera de schema
- propone una acción inexistente
- propone algo no autorizado

entonces el sistema:

- no ejecuta nada
- audita el rechazo
- responde con ayuda cerrada o cae al modo por reglas

## auditoría propuesta

Eventos adicionales:

- `llm_invoked`
- `llm_output_validated`
- `llm_output_rejected`
- `response_generated`

Se mantienen:

- `assistant_wake`
- `assistant_sleep`
- `intent_detected`
- `intent_rejected_unsupported`
- `intent_rejected_unauthorized`
- `confirmation_requested`
- `confirmation_accepted`
- `confirmation_rejected`
- `action_executed`
- `action_failed`

## aislamiento del runtime

El bot/adapter debe seguir corriendo con aislamiento fuerte:

- usuario de sistema dedicado
- sin shell arbitraria
- sin sudo general
- acceso solo a policy, audit, runtime state y broker
- red solo hacia Telegram y proveedor LLM si se activa

El LLM no debe recibir:

- secretos del host
- rutas amplias del sistema
- contenido libre del filesystem
- comandos internos

## proveedor LLM

Se puede usar un proveedor ligero y rápido como Gemini Flash o equivalente, pero siempre como adapter opcional.

Variables de entorno sugeridas:

- `OPENCLAW_LLM_ENABLED=true|false`
- `OPENCLAW_LLM_PROVIDER=gemini`
- `OPENCLAW_LLM_MODEL=gemini-2.5-flash`
- `OPENCLAW_LLM_API_KEY=...`
- `OPENCLAW_LLM_TIMEOUT_SECONDS=5`

Todas fuera del repo.

## estrategia recomendada

Implementar `B sobre A`:

- conservar el modo cerrado actual
- añadir adapter LLM solo como fallback en `wake`
- mantener mutaciones con confirmación y validación local

No hacer todavía:

- bot nuevo separado
- tools abiertas
- shell controlada por modelo
- acceso amplio al VPS

## plan de implementación fase 16

1. Añadir `llm_adapter.py`
2. Añadir schema cerrado para intents
3. Integrar invocación opcional del LLM en `wake mode`
4. Mantener fallback a reglas
5. Auditar invocación y validación
6. Añadir tests de:
   - output válido
   - output inválido
   - fallback seguro
   - mutación con confirmación
   - rechazo de acción no autorizada

## criterio de éxito

- Telegram se siente más natural
- no existe ejecución arbitraria
- el modelo de seguridad actual se mantiene
- el proyecto no se desvía hacia un agente libre
- el operador conserva trazabilidad y control
