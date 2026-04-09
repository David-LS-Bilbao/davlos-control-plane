## Alcance

Este documento resume los flujos operativos MVP validados sobre OpenClaw con las piezas ya existentes:

- DAVLOS VPN Console
- restricted operator broker
- policy viva con TTL y one-shot
- operator auth mínima
- canal Telegram privado MVP

No introduce nuevas capacidades. Su objetivo es medir fricción real de operador antes de abrir más superficie.

## Flujos Validados

### 1. Observabilidad diaria desde consola

Herramienta:
- `bash scripts/console/davlos-vpn-console.sh openclaw-capabilities`
- `bash scripts/console/davlos-vpn-console.sh openclaw-diagnostics`

Resultado:
- la consola muestra estado efectivo legible
- el operador ve `status`, `mode`, `allowed`, `permission`
- cuando aplica, también ve `expires_at`, `one_shot` y `consumed`
- con el helper readonly instalado, la vista puede seguir saliendo del runtime real cuando el problema es de permisos de lectura sobre `/opt/automation`

Valor operativo:
- sirve como vista rápida diaria del boundary de capacidades
- no obliga a leer JSON ni a inspeccionar la policy a mano

Fricción residual:
- si se quiere ver trazabilidad real, hay que mirar el audit log activo; la plantilla del repo sigue siendo declarativa
- sin helper readonly o permisos equivalentes, la visibilidad del runtime puede degradarse; y si el fallo no es de permisos, la consola no siempre puede recuperar la vista real

### 2. Habilitar una capacidad con TTL

Herramienta:
- `python3 scripts/agents/openclaw/restricted_operator/cli.py --policy <policy> enable --action-id action.dropzone.write.v1 --ttl-minutes 30 --operator-id <operator>`

Resultado:
- la operación deja `enabled=true` y `expires_at` de forma coherente
- la vista `show --format console` permite comprobarlo rápido

Valor operativo:
- flujo útil para apertura temporal de capacidad sin tocar JSON
- el resultado es comprensible para un operador sin contexto de implementación

Fricción residual:
- para pruebas reales conviene una policy temporal aislada, porque la plantilla del repo representa contrato y no estado operativo vivo

### 3. Consumir y resetear una capacidad one-shot

Herramientas:
- `consume-one-shot`
- `reset-one-shot`

Resultado:
- el flujo funciona cuando se ejecuta sobre una policy/runtime coherentes
- la auditoría deja eventos visibles de consumo y reset

Valor operativo:
- permite modelar permisos de uso único sin inventar otro mecanismo

Fricción residual:
- el operador necesita entender que `one_shot` depende de estado runtime, no solo del JSON versionado
- si no se lee el runtime real o se mezcla plantilla declarativa con state store viejo, la lectura puede resultar confusa

### 4. Ejecutar una acción permitida por Telegram

Herramienta:
- `/status`
- `/execute action.logs.read.v1 stream_id=openclaw_runtime tail_lines=2`
- `/audit_tail`

Resultado:
- Telegram sirve como canal ligero para consulta y ejecución cerrada
- la autorización respeta `chat_id`/`user_id` mapeados a `operator_id`
- la auditoría conserva trazabilidad útil

Valor operativo:
- resuelve consultas rápidas sin entrar a la consola
- es suficiente para operaciones pequeñas de guardia o verificación

Fricción residual:
- los payloads siguen siendo austeros y poco ergonómicos en formato `k=v`
- es útil para acciones cerradas y pequeñas, pero no para flujos más densos

## Qué Funciona Bien

- La consola ya es suficiente para operar capacidades OpenClaw sin otra UI.
- El helper readonly reduce mucho la fricción entre policy declarativa y runtime real.
- El helper readonly sigue siendo una superficie cerrada; no equivale a abrir `journald` general ni `/opt/automation` completo.
- La policy viva con TTL y one-shot cubre el ciclo básico de apertura, consumo y cierre.
- Telegram aporta valor como canal corto de consulta/ejecución.
- La trazabilidad mínima es suficiente para una operación MVP disciplinada.

## Fricciones Reales Detectadas

- La diferencia conceptual entre policy declarada y runtime state sigue existiendo para un operador nuevo, aunque la consola la mitiga mejor si el helper readonly está activo.
- Sin helper readonly o permisos equivalentes, la auditoría y el estado real pueden degradarse aunque el sistema siga operativo.
- Telegram es práctico para comandos breves, pero el formato de parámetros no escala bien a payloads más ricos.
- Faltan algunas acciones operativas pequeñas si se quisiera ampliar uso diario, por ejemplo verificaciones o lecturas más específicas; eso no bloquea el MVP actual.

## Decisión Recomendada

No hace falta abrir chat web todavía.

La recomendación es:

1. seguir usando DAVLOS VPN Console como herramienta principal de operación
2. mantener Telegram como canal ligero de consulta y ejecución cerrada
3. si se necesita una siguiente inversión funcional, priorizar una o dos acciones concretas de broker de alto valor antes que una nueva UI

## Siguiente Paso Recomendado

La siguiente inversión útil no es otro canal, sino una de estas dos opciones:

- añadir una acción nueva y cerrada de alto valor operativo
- o ampliar la observabilidad y ergonomía sobre el runtime activo ya existente

Mientras eso no sea necesario, el sistema actual ya soporta pruebas operativas reales con fricción razonable.
