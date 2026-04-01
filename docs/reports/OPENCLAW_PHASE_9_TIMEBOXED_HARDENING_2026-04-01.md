# OPENCLAW PHASE 9 TIME-BOXED HARDENING

## alcance real

Fase corta centrada en tres bloques:

1. pin por digest
2. normalización mínima/persistente de UFW
3. evaluación de allowlist de egress para `agents_net`

## cambios aplicados realmente

### pin por digest

Se resolvió el digest real del runtime:

- `ghcr.io/openclaw/openclaw@sha256:acc3631077173c8050278a44896947b6052dd5c8ebace4ee1a452a276bd28bab`

Se aplicó a plantillas y defaults de despliegue.

### UFW

Se corrigió el drift más peligroso:

- `ENABLED=no` -> `ENABLED=yes` en `/etc/ufw/ufw.conf`

Se endureció además una regla amplia de poco valor:

- eliminada la regla temporal `11434/tcp any-dst` para `agents_net`

### allowlist de egress

No se aplicó una allowlist real de egress en esta fase.

Razón:

- el coste/riesgo de hacerlo bien supera el time-box actual
- la reachability de OpenClaw no debía ponerse en riesgo

## validaciones

- `docker exec openclaw-gateway ... fetch('http://172.22.0.1:11440/healthz')` OK
- `curl http://127.0.0.1:11440/healthz` OK
- `curl http://212.227.159.131:11440/healthz` sigue fallando desde IP pública
- `ufw status numbered` confirma desaparición de la regla temporal amplia
- `/etc/ufw/ufw.conf` confirma `ENABLED=yes`

## deuda técnica formal

- simplificación posterior de reglas históricas UFW
- allowlist de egress real para `agents_net`
- refresh deliberado del runtime para consumir explícitamente el digest ya fijado

## decisión

Éxito de fase alcanzado:

- se capturó valor real y pequeño de hardening
- no se retrasó el proyecto
- quedó claro qué se resolvió ahora y qué se difiere
