# OPENCLAW Phase 15 Wake Mode

Fecha: 2026-04-01
Rama: `codex/openclaw-console-readonly`

## objetivo

Evolucionar el bot Telegram desde un modo conversacional básico por reglas hacia un modo asistente `wake/sleep`, manteniendo intacto el modelo de seguridad actual.

## cambios aplicados

- sesión efímera por `chat_id:user_id`
- comandos `/wake` y `/sleep`
- timeout por inactividad
- integración con el modo conversacional previo
- respuestas más naturales en modo despierto
- confirmación mutante mantenida
- rechazo temprano de mutaciones fuera de permisos
- auditoría adicional de sesión y respuestas

## alcance funcional

En modo despierto:

- consulta de estado general
- consulta de capacidades activas
- consulta de auditoría reciente
- consulta de logs permitidos
- explicación resumida del estado
- propuesta textual de acción segura

Mutaciones soportadas:

- habilitar/deshabilitar capacidad
- habilitar con TTL
- resetear one-shot

## seguridad

- no se añadió shell arbitraria
- no se añadió ejecución libre
- la allowlist Telegram sigue resolviendo `operator_id`
- la autorización sigue pasando por `operator_auth`
- la ejecución real sigue pasando por broker o mutaciones controladas de policy

## tests

Cobertura añadida:

- `wake`
- `sleep`
- timeout
- consulta natural en modo despierto
- mutación con confirmación en modo despierto
- rechazo de mutación fuera de permisos

Comando de validación:

```bash
python3 -m unittest tests.restricted_operator.test_broker
```

## riesgos residuales

- la sesión y la confirmación pendiente siguen en memoria del proceso
- el lenguaje soportado sigue siendo deliberadamente estrecho
- no hay persistencia cross-restart de contexto conversacional

## salida

Esta fase deja Telegram en un punto útil de “asistente despierto” sin romper el perímetro actual de seguridad.
