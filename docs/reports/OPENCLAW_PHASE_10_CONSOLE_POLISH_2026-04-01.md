# OPENCLAW PHASE 10 CONSOLE POLISH

## alcance

Mini-fase de pulido operator-focused sobre la DAVLOS VPN Console MVP.

Fuera de alcance:

- nuevas features
- UI web
- cambios de arquitectura del broker

## problemas detectados

- lectura incómoda del estado de capacidades
- falta de separación visual entre acciones readonly y mutantes
- feedback poco claro al fallar una mutación

## cambios aplicados

- formato `console` en la CLI para:
  - `show`
  - `audit-tail`
- submenú OpenClaw con etiquetas explícitas:
  - `[readonly]`
  - `[mutating]`
- mejora de ayuda y copy del menú
- mensajes de error más útiles en mutaciones

## validaciones

- `bash -n scripts/console/davlos-vpn-console.sh`
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy ... show --format console`
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy ... audit-tail --format console`
- smoke test de:
  - `bash scripts/console/davlos-vpn-console.sh openclaw-capabilities`
  - `bash scripts/console/davlos-vpn-console.sh openclaw-capabilities-audit`

## resultado

La consola queda más clara para operación real:

- el operador entiende mejor el estado efectivo de cada capacidad
- distingue mejor qué puede ver y qué puede cambiar
- recibe feedback más útil sin salir del flujo del menú
