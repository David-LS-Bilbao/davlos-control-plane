# OpenClaw Phase 4 Console Capabilities 2026-04-01

## objetivo

Integrar la gestión de capacidades OpenClaw en la DAVLOS VPN Console, reutilizando la CLI y la política viva del broker sin duplicar lógica de seguridad en Bash.

## diseño aplicado

### integración

La consola:

- no modifica JSON directamente
- usa la CLI del broker como capa única de política
- degrada con mensaje claro si faltan permisos

### operaciones soportadas

- ver acciones conocidas y estado efectivo
- habilitar una acción
- deshabilitar una acción
- habilitar una acción con TTL
- resetear consumo `one_shot`
- ver auditoría reciente

## cambios implementados

### consola

Se extendió:

- `scripts/console/davlos-vpn-console.sh`

Nuevo submenú:

- `OpenClaw / capacidades`

Accesos directos:

- `openclaw-capabilities`
- `openclaw-capabilities-audit`

### CLI

Se ampliaron utilidades mínimas en:

- `scripts/agents/openclaw/restricted_operator/cli.py`

Subcomandos añadidos:

- `enable`
- `disable`
- `set-ttl`
- `clear-ttl`
- `reset-one-shot`
- `audit-tail`

Además:

- `enable --ttl-minutes` permite el flujo de “habilitar con TTL” sin editar policy a mano

### state/policy layer

Se añadieron operaciones seguras en:

- `scripts/agents/openclaw/restricted_operator/policy.py`

Para:

- habilitar
- deshabilitar
- fijar expiración
- limpiar expiración
- resetear consumo `one_shot`

## validación ejecutada

### técnica

- `bash -n scripts/console/davlos-vpn-console.sh`
- `python3 -m unittest tests.restricted_operator.test_broker`

Resultado:

- sintaxis Bash correcta
- 9 tests correctos

### flujo operador sobre policy temporal aislada

Validado con policy en `/tmp/davlos_broker_console_test/policy.json`:

- `show`
- `disable action.dropzone.write.v1`
- `enable action.dropzone.write.v1 --ttl-minutes 15`
- `consume-one-shot action.webhook.trigger.v1`
- `reset-one-shot action.webhook.trigger.v1`
- `audit-tail --lines 10`

Resultado:

- listado de acciones correcto
- cambio `enabled=false` correcto
- cambio `enabled=true + expires_at` correcto
- consumo y reset de `one_shot` correctos
- auditoría reciente visible con eventos de cambio

## archivos creados o modificados

### creados

- `docs/CONSOLE_OPENCLAW_CAPABILITIES_MVP.md`
- `docs/reports/OPENCLAW_PHASE_4_CONSOLE_CAPABILITIES_2026-04-01.md`

### modificados

- `scripts/console/davlos-vpn-console.sh`
- `scripts/agents/openclaw/restricted_operator/cli.py`
- `scripts/agents/openclaw/restricted_operator/policy.py`
- `tests/restricted_operator/test_broker.py`

## riesgos residuales

- la consola todavía no tiene autenticación fuerte final
- los cambios siguen dependiendo de permisos efectivos sobre el state store
- la selección de action IDs sigue siendo textual, no asistida por UI rica
- la acción de restart sigue fuera del menú por seguridad

## qué queda listo para la fase siguiente

- canal externo futuro hacia el broker sin acceso libre
- integración posterior con Telegram/chat o canal equivalente
- capa de autorización más fuerte sobre un flujo ya operativo
- menú final de capacidades sin rehacer la política ni la auditoría

## decisión

### decisión

`GO` para la siguiente fase.

### motivo

El operador ya puede gestionar capacidades OpenClaw desde la DAVLOS VPN Console utilizando la política viva y la CLI existentes, sin romper el modelo de seguridad actual.
