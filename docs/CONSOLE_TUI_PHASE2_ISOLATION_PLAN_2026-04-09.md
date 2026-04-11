# Console TUI Phase 2 Isolation Plan

Fecha: `2026-04-09`

## Objetivo

Actualizar la consola `scripts/console/davlos-vpn-console.sh` hacia una TUI mas navegable y ergonomica, pero sin mezclar ese trabajo con cambios sensibles de runtime, broker, Telegram, policy o LLM.

## Baseline de partida

- El fix de paridad repo/host del helper readonly queda tratado por la PR `#5`.
- El runtime real del VPS ya valida:
  - helper readonly usable desde `devops`
  - broker state/audit visibles via helper
  - Telegram runtime visible via helper
- La rama `codex/console-tui-navigation-wip-20260402` contiene trabajo util de TUI, pero hoy mezcla:
  - mejoras puras de navegacion/presentacion
  - cambios de runtime y seguridad
  - cambios de Telegram/assistant
  - cambios de `policy.py` y `state_store.py`

## Regla de aislamiento

La Fase 2 solo puede tocar estos ficheros:

- `scripts/console/davlos-vpn-console.sh`
- `docs/CONSOLE_TUI_PHASE2_ISOLATION_PLAN_2026-04-09.md`
- documentacion minima adicional estrictamente necesaria para la TUI

Quedan explicitamente fuera:

- `scripts/agents/openclaw/restricted_operator/policy.py`
- `scripts/agents/openclaw/restricted_operator/state_store.py`
- `scripts/agents/openclaw/restricted_operator/telegram_bot.py`
- cualquier fichero de assistant/LLM/intent router
- templates host-side distintos del helper ya alineado por la PR `#5`

## Cambios TUI permitidos

Se pueden extraer de la rama WIP solo los cambios de UI local que no alteren contratos de runtime:

- header visual mejorado
- fallback compacto para terminales estrechas
- metricas de CPU/RAM/hora
- menus interactivos con flechas y `j/k`
- selector guiado de acciones mutantes
- reorganizacion del menu principal por dominios
- vistas de ayuda mas claras
- atajos de navegacion puramente locales

## Cambios TUI prohibidos en Fase 2

- abrir nuevas capacidades mutantes no existentes en la policy viva
- cambiar el significado de acciones o permisos
- introducir dependencias externas
- depender de rutas nuevas de runtime
- acoplar la TUI a nuevos formatos de estado
- mezclar backups, boundary o Telegram assistant dentro del mismo diff salvo renderizado puro ya soportado

## Secuencia recomendada

### Fase 2.1: Extraer solo presentacion y navegacion

- cherry-pick manual de bloques UI de `davlos-vpn-console.sh`
- mantener el mismo contrato de comandos:
  - `overview`
  - `openclaw`
  - `openclaw-capabilities`
  - `openclaw-capabilities-audit`
  - `openclaw-telegram`
  - `openclaw-diagnostics`
- no tocar los caminos de ejecucion del broker mas alla del render/menu

### Fase 2.2: Endurecer compatibilidad de terminal

- modo Unicode normal
- fallback ASCII-safe opcional
- no asumir soporte de emoji o glifos especiales
- soportar sesiones interactivas y no interactivas sin degradar automatizaciones

### Fase 2.3: Validacion operativa

- `bash -n scripts/console/davlos-vpn-console.sh`
- `printf '9\n' | env -u TERM bash scripts/console/davlos-vpn-console.sh`
- validacion TTY real de:
  - menu principal
  - OpenClaw y Telegram
  - Broker y capacidades
  - Seguridad y control
- validacion real en VPS como `devops`:
  - `overview`
  - `openclaw-capabilities`
  - `openclaw-capabilities-audit`
  - `openclaw-telegram`

### Fase 2.4: Merge separado

- PR dedicada solo a TUI
- sin mezclar con cambios de runtime
- diff revisable casi integro sobre `davlos-vpn-console.sh`

## Criterios de aceptacion

- la consola mejora navegacion sin cambiar comportamiento operativo
- `devops` sigue viendo el runtime real via helper
- las rutas readonly y mutating existentes conservan el mismo significado
- la ejecucion no requiere dependencias nuevas
- la consola sigue funcionando en modo no interactivo

## Riesgos a vigilar

- que el redibujado rompa sesiones no TTY
- que el uso de Unicode degrade terminales pobres
- que un cherry-pick parcial de la rama WIP arrastre cambios de runtime no deseados
- que el selector guiado de acciones enmascare errores reales de autorizacion

## Resultado esperado

Dos PRs separadas y auditables:

1. PR `#5`: paridad helper/runtime ya validada
2. PR nueva de Fase 2: solo TUI/navegacion/presentacion
