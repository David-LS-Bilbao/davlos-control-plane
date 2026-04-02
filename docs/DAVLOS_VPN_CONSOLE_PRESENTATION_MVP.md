# DAVLOS VPN Console Presentation MVP

## objetivo

Mejorar la presentación de la DAVLOS VPN Console sin reescribirla, sin meter dependencias nuevas y sin mover lógica real de seguridad al Bash.

## fricciones visuales detectadas

- cabecera demasiado plana y poco memorable
- menús funcionales pero con poca jerarquía visual
- bloques con demasiado `key=value` seguidos sin contexto
- poca diferenciación entre lectura, mutación, warning y error
- ayudas útiles, pero poco presentables para demo

## criterios aplicados

- polish visual ligero, no nueva arquitectura
- degradación limpia en terminal básica sin color
- color ANSI solo si el terminal lo permite
- lenguaje corto y claro para operador no experto
- mantener toda la lógica real fuera del Bash

## cambios aplicados

### cabecera

- marca textual `DAVLOS CONTROL-PLANE`
- subtítulo `VPN Console MVP`
- separadores más limpios
- contexto visible de `repo` y `timestamp`

### jerarquía visual

- títulos de sección más claros
- subtítulos homogéneos por bloque
- alineación de pares clave/valor con columna estable

### badges semánticos

Se añadieron etiquetas visuales degradables:

- `READONLY`
- `MUTATING`
- `SUCCESS`
- `WARNING`
- `ERROR`

### menús

- menú principal más limpio
- submenús más enseñables
- señalización explícita de `READONLY` y `READ + MUTATE`

### mensajes operativos

- avisos de falta de acceso a Docker o journal más claros
- mensajes de éxito/error de cambios de capacidad más visibles
- ayudas del apartado OpenClaw más cortas y más legibles

## fuera de alcance

- reescribir la consola como TUI
- añadir dependencias de styling
- mover auth, policy, broker o auditoría al Bash
- crear nuevas capacidades del broker
- abrir otros canales distintos de Telegram

## validación mínima sugerida

```bash
bash -n scripts/console/davlos-vpn-console.sh
bash scripts/console/davlos-vpn-console.sh help
bash scripts/console/davlos-vpn-console.sh host
bash scripts/console/davlos-vpn-console.sh openclaw
bash scripts/console/davlos-vpn-console.sh openclaw-capabilities
```

## resultado esperado

La consola sigue siendo simple y operativa, pero ahora se puede enseñar mejor en demo sin parecer un borrador técnico.
