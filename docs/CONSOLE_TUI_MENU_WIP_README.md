# Console TUI Menu WIP

Estado guardado para continuar el trabajo del menu TUI de `scripts/console/davlos-vpn-console.sh`.

## Rama de trabajo

- Rama actual: `codex/console-tui-navigation-wip-20260402`

## Objetivo ya completado

- Header superior refactorizado con panel verde, banner DAVLOS centrado y fallback compacto para terminales estrechas.
- Guardas seguras para `clear` en entornos no interactivos.
- Metricas reales en header:
  - CPU con fallback a `/proc/stat`
  - RAM con `free -m`
  - Hora forzada a `Europe/Madrid`
- Menus interactivos con flechas `Up/Down` y `Enter` usando `read -rsn1`.
- Redibujado limitado a la zona del menu para no destruir el header.
- Fallback no interactivo mantenido para sesiones sin TTY.

## Menus ya migrados a `interactive_menu`

- Menu principal
- OpenClaw y Telegram
- Broker y capacidades
- Seguridad y control
- Diagnostico
- Broker / control manual
- Selector de accion mutante

## Helpers nuevos relevantes

- `panel_text_length`
- `panel_truncate_text`
- `panel_row`
- `panel_center_line`
- `panel_rule`
- `panel_metric_cpu`
- `panel_metric_ram`
- `panel_metric_vpn_nodes`
- `panel_terminal_width`
- `interactive_menu_render`
- `interactive_menu`
- `menu_choice_with_fallback`
- `inline_menu_choice_with_fallback`
- `init_menu_options`

## Validacion ya hecha

- `bash -n scripts/console/davlos-vpn-console.sh`
- `printf '9\n' | env -u TERM bash scripts/console/davlos-vpn-console.sh`
- Prueba TTY real del menu principal
- Prueba TTY real entrando en `Broker y capacidades` y volviendo con `Volver`

## Comportamiento actual

- En TTY:
  - Se muestra cursor visual `❯`
  - Soporta flechas `Up/Down`
  - Soporta `j/k` como alias de navegacion
  - `Enter` devuelve el id de opcion y ejecuta la rama existente
- Sin TTY:
  - Se usa `show_*` + `read -r` como antes

## Limitaciones conocidas

- La seleccion actual siempre arranca en la primera opcion al volver a un menu.
- No hay soporte aun para `Home`, `End`, `Esc` o `q`.
- No hay memoria de ultima opcion por submenu.
- El cursor `❯` y algunos emojis del texto pueden depender del terminal del operador.

## Proximo paso recomendado

1. Persistir la opcion activa por menu para mejorar la navegacion repetida.
2. Anadir atajos `Esc` o `q` para volver atras sin tener que ir a `Volver`.
3. Introducir un modo ASCII-safe opcional para terminales con render Unicode pobre.
4. Conectar `Nodos VPN` a una fuente real de runtime cuando se defina la fuente de verdad.

## Ficheros que pertenecen a este trabajo

- `scripts/console/davlos-vpn-console.sh`
- `docs/CONSOLE_TUI_MENU_WIP_README.md`

## Nota de alcance

El arbol git contiene otros cambios no relacionados. Para este checkpoint solo deben staged/committearse los dos ficheros anteriores.
