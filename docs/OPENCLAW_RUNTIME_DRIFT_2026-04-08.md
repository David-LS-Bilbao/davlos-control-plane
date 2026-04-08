# OpenClaw Runtime Drift 2026-04-08

## propósito

Dejar una referencia documental mínima y explícita sobre drift conocido entre:

- diseño y documentación del repo;
- plantillas y scripts versionados;
- estado host observado en auditorías previas.

Este documento no valida el host por sí solo.
Tampoco autoriza redeploy, rollback ni cambios de runtime.

## alcance

Este documento cubre solo drift relevante para operar OpenClaw con prudencia:

- ownership y permisos;
- helper readonly;
- Telegram runtime;
- staging vs deploy;
- bind loopback vs `bind: "lan"`;
- template `compose` vs runtime vivo;
- observabilidad.

Todo lo no confirmado aquí debe seguir etiquetado como `pendiente de verificación en host`.

## tabla de drift conocido

| área | diseño/documentación | plantilla o repo | estado host observado | riesgo | decisión temporal |
| --- | --- | --- | --- | --- | --- |
| ownership y permisos | mínimo privilegio y separación de roles | scripts y docs históricamente no dejaban este reparto suficientemente explícito | ownership mixto observado: `root` conserva `compose`, `broker`, `dropzone` y secretos; `devops` posee `config`, `state` y `logs` | cambiar ownership por simplificación puede ampliar superficie o romper controles | documentar el reparto actual como deliberado; no proponer `chown -R` |
| helper readonly | observabilidad controlada sin abrir `/opt/automation` | la documentación quedó en versión de 4 modos | el helper observado expone 5 modos, incluido `operational_logs_recent` | documentación incompleta induce validaciones parciales o instalación incorrecta | tratar el helper como vía preferente de observabilidad controlada y actualizar docs |
| Telegram runtime | Telegram persistente y acotado por broker/policy | el repo ya documenta runtime persistente, pero la telemetría sigue mínima | servicio operativo con degradación intermitente de polling y estado persistente mínimo | venderlo como “cerrado” ocultaría degradación real | mantener estado operativo pero degradado; no ampliar claims |
| staging vs deploy | staging y validación previa al deploy | `scripts/agents/openclaw/README.md` llamaba staging a todo el tramo | `30_first_local_deploy.sh` sí crea red, copia runtime, valida upstream y despliega con Docker | confusión documental puede empujar a ejecución equivocada | separar explícitamente staging, prechecks y deploy real |
| bind loopback vs `bind: "lan"` | gateway northbound local-only | `openclaw.json.example` mantiene `bind: "lan"` | publish observado del host en `127.0.0.1:18789` | corregir la config a ciegas podría cambiar semántica del runtime | tratarlo como drift contractual; documentar y dejar decisión pendiente |
| compose/template vs runtime vivo | el repo ofrece contrato de despliegue base | plantilla `docker-compose` no coincide exactamente con el `compose` vivo en healthcheck y detalles de arranque | runtime observado sano, pero con diferencias materiales frente a plantilla | redeploy ciego puede reintroducir drift o cambiar comportamiento | no redeployar a ciegas; revisar drift antes de tocar runtime |
| observabilidad | helper readonly y consola como baseline seguro | faltaba un documento único de drift y faltaba precheck readonly del repo | la operación depende de distinguir documentación, plantilla y estado observado | sin precheck, el repo puede volver a divergir sin señal temprana | añadir documento formal de drift y precheck readonly de coherencia |

## ownership y permisos

Estado observado y ya auditado:

- `root` conserva `compose`, `broker`, `dropzone` y secretos;
- `devops` posee `config`, `state` y `logs`.

Juicio documental:

- este reparto debe considerarse deliberado y alineado con mínimo privilegio;
- no debe proponerse `chown -R` completo a `devops` como “simplificación”;
- si en el futuro hiciera falta más lectura operativa para `devops`, la vía preferente sigue siendo helper readonly o un mecanismo acotado equivalente, no apertura general del runtime.

## helper readonly

Estado observado:

- existe helper readonly host-side;
- la interfaz observada incluye cinco modos:
  - `runtime_summary`
  - `broker_state_console`
  - `broker_audit_recent`
  - `telegram_runtime_status`
  - `operational_logs_recent`

Decisión temporal:

- la documentación del repo debe reflejar ya esos cinco modos;
- no ampliar el helper a mutaciones;
- mantenerlo como vía preferente de observabilidad controlada.

## Telegram runtime

Estado observado:

- Telegram persiste estado runtime mínimo;
- la operación existe, pero con degradación/intermitencia de polling.

Decisión temporal:

- documentar Telegram como operativo y persistente;
- no vender cierre funcional completo;
- dejar explícito que la telemetría sigue siendo limitada para una operación madura.

## staging vs deploy

Drift confirmado:

- `10_stage_runtime.sh` y `20_validate_runtime_readiness.sh` siguen siendo de staging y precheck;
- `30_first_local_deploy.sh` ya no es staging: despliega runtime real con Docker y toca artefactos vivos del runtime.

Decisión temporal:

- la documentación debe separar esos tramos;
- no ejecutar `30_first_local_deploy.sh` como si fuera un paso inocuo de scaffold.

## bind loopback vs `bind: "lan"`

Estado documental:

- el diseño northbound vigente vende exposición local-only;
- `templates/openclaw/openclaw.json.example` mantiene `bind: "lan"`.

Estado host observado:

- publish northbound del gateway en `127.0.0.1:18789`.

Juicio técnico:

- el control local-only observado está asegurado northbound por publish loopback en host;
- persiste un drift semántico entre ese publish y `bind: "lan"` en config;
- no debe corregirse el runtime por reflejo documental.

## compose/template vs runtime vivo

Estado documental:

- el repo contiene plantillas versionadas para componer un despliegue reproducible.

Riesgo actual:

- si la plantilla y el runtime vivo divergen materialmente, un redeploy a ciegas puede introducir cambios no revisados.

Decisión temporal:

- tratar el `compose` versionado como baseline declarativa, no como espejo exacto del runtime vivo;
- exigir precheck de drift del repo antes de cualquier intervención posterior.

## observabilidad

Postura vigente:

- el helper readonly es la vía preferente de observabilidad controlada;
- la consola puede degradar de lectura directa a helper sin abrir permisos generales;
- faltaba un documento formal de drift y un precheck de coherencia del repo.

Con este documento y el script `scripts/agents/openclaw/40_runtime_drift_readonly.sh`, el repo gana una barrera documental mínima antes de cualquier redeploy o refactor operativo posterior.

## qué no hacer todavía

- no redeployar a ciegas mientras exista drift material repo/host;
- no corregir funcionalmente `templates/openclaw/docker-compose.yaml`;
- no corregir funcionalmente `templates/openclaw/openclaw.json.example`;
- no modificar units `systemd`, sudoers ni scripts mutantes solo para “alinear” el repo;
- no proponer `chown -R` completo a `devops`;
- no vender como validado en host nada que aquí solo quede documentado.

## parche pendiente para obsi-claw-AI_agent

Parche textual pendiente para aplicar manualmente en:

- `docs/evidence/VALIDACION_HELPER_READONLY_SPRINT_1.md`

Cambios recomendados:

- sustituir toda referencia a “cuatro modos” por “cinco modos”;
- actualizar la línea de `Usage` para incluir `operational_logs_recent`;
- ampliar la tabla de validación con una fila específica para `operational_logs_recent`;
- ajustar el resumen ejecutivo para indicar que el helper observado ya cubre también logs operativos recientes de unidades permitidas;
- mantener explícito que sigue siendo readonly y que esto no amplía permisos mutantes ni acceso general a `/opt/automation`.
