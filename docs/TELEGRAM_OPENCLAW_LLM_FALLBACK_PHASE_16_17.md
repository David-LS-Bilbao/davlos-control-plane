# Telegram OpenClaw LLM Fallback Phase 16-17

## objetivo

Describir el estado operativo actual del canal Telegram de OpenClaw tras las Fases 16 y 17:

- fallback LLM controlado sobre el asistente existente
- `local-first` intacto
- mejora de UX conversacional sin cambiar seguridad ni ejecución real

## principios mantenidos

- Telegram sigue siendo solo canal.
- `operator_auth`, policy viva y auditoría siguen mandando.
- El broker restringido y la ruta actual de mutaciones siguen siendo el plano real de ejecución.
- No hay shell arbitraria.
- No hay tools abiertas ni acceso libre al filesystem.
- Las mutaciones siguen bajo confirmación explícita.

## modelo operativo actual

Flujo conceptual:

1. Telegram recibe mensaje.
2. Se resuelve `chat_id/user_id -> operator_id`.
3. Slash commands y confirmaciones siguen por reglas.
4. En conversación:
   - primero se intenta matcher local
   - solo si la sesión está en `wake` y el matcher no resuelve, entra el fallback LLM
5. La salida LLM se valida localmente contra un contrato cerrado.
6. Lecturas, propuestas y confirmaciones siguen pasando por auth/policy/ruta actual/auditoría.

## local-first y wake mode

- Fuera de `wake`, no se usa LLM.
- En `wake`, las frases ya cubiertas por reglas siguen resolviéndose por reglas.
- El LLM solo entra como fallback sobre frases abiertas o ambiguas no resueltas localmente.

Ejemplos que siguen por reglas:

- `quien eres`
- `como estamos`
- `que puedes hacer`
- confirmaciones `si/no`
- slash commands como `/status` y `/capabilities`

## contrato cerrado del LLM

El LLM no ejecuta nada. Solo devuelve una salida estructurada cerrada para:

- `status`
- `capabilities`
- `audit_tail`
- `logs_read`
- `explain_status`
- `suggest_action`
- `enable_capability`
- `disable_capability`
- `enable_capability_with_ttl`
- `reset_one_shot`
- `unsupported`

La salida se valida localmente:

- JSON válido
- sin claves extra
- `intent` dentro de allowlist
- `action_id` coherente con el intent
- `params` tipados y restringidos
- `needs_confirmation` coherente con lectura o mutación

Si falla esa validación, el sistema no ejecuta nada y cae al modo seguro.

## qué sigue yendo por reglas

- slash commands
- `wake/sleep`
- confirmaciones `si/no`
- intents ya cubiertos por matcher local
- ejecución real de lecturas y mutaciones
- confirmación obligatoria para mutaciones

## mejoras introducidas por fase 17

### suggest_action

Se afinó el comportamiento para que la recomendación sea más prudente:

- prioriza auditoría, capacidades y logs permitidos
- evita proponer de primeras acciones sensibles de control
- si llegara a sugerir un cambio, lo presenta como propuesta prudente, no como recomendación fuerte

### explain_status

Se mejoró la explicación conceptual de estados:

- `enabled`: capacidad disponible ahora mismo
- `disabled`: capacidad cerrada explícitamente
- `expired`: capacidad cuyo TTL ya venció
- `consumed` / `one-shot`: capacidad de un solo uso ya consumida

La respuesta ya no se limita a repetir el bloque de estado actual.

## auditoría relevante

Eventos añadidos o usados en esta capa:

- `llm_invoked`
- `llm_output_validated`
- `llm_output_rejected`
- `intent_detected`
- `intent_rejected_unsupported`
- `confirmation_requested`
- `confirmation_accepted`
- `confirmation_rejected`
- `response_generated`

## límites conocidos

- no es un chatbot libre
- no hay shell
- no hay tools abiertas
- no hay memoria larga
- mutaciones requieren confirmación
- la calidad del fallback depende del prompt y del modelo

## estado real actual del runtime

Estado actual confirmado:

- Gemini activo en runtime real como fallback controlado
- `local-first` intacto
- sin alterar el perímetro `auth/policy/broker`
- slash commands y confirmaciones siguen por reglas
- mutaciones siguen bajo confirmación estricta

## validación funcional real en Telegram

Validación mínima ya comprobada en operación:

- `/status` OK
- `/capabilities` OK
- frases conocidas por reglas en `wake` OK
- frase abierta en `wake` usando fallback LLM OK
- mutación sin confirmación no se ejecuta
- auditoría de `llm_invoked` y `llm_output_validated` / `llm_output_rejected` OK
