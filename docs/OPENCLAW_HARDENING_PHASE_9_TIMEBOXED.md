# OpenClaw Hardening Phase 9 Time-Boxed

## objetivo

Capturar endurecimientos de alto valor y baja fricción sin bloquear la ejecución principal del proyecto.

## bloques evaluados

### 1. pin por digest

Resuelto en esta fase.

Se obtuvo el digest real de la imagen actualmente usada por `openclaw-gateway`:

- `ghcr.io/openclaw/openclaw@sha256:acc3631077173c8050278a44896947b6052dd5c8ebace4ee1a452a276bd28bab`

Se fijó en:

- `templates/openclaw/openclaw.env.example`
- `scripts/agents/openclaw/30_first_local_deploy.sh`
- `runbooks/OPENCLAW_DEPLOY_MVP.md`

Decisión:

- no recrear el contenedor actual solo por esta fase
- usar el digest ya resuelto para siguientes despliegues o reprovisionados

### 2. normalización mínima de UFW

Resuelto en esta fase.

Cambios aplicados:

- `ENABLED=yes` en `/etc/ufw/ufw.conf` para alinear persistencia con runtime activo
- eliminación de la regla temporal amplia `allow agents to host ollama any-dst` en `11434/tcp` para `agents_net`

Se mantienen reglas específicas ya necesarias:

- `172.22.0.1:11434`
- `172.17.0.1:11434`
- `11440/tcp` para `inference-gateway`

### 3. allowlist de egress para agents_net

Diferido.

Motivo:

- una allowlist real de egress exige validar con más cuidado todos los destinos mínimos del runtime
- un cambio precipitado aquí sí podría romper operación real

Contrato de siguiente paso:

1. enumerar destinos necesarios de OpenClaw
2. mantener explícitamente `172.22.0.1:11440`
3. decidir si `11434` directo sigue siendo necesario o puede eliminarse completamente
4. aplicar allowlist pequeña sobre `DOCKER-USER` o política equivalente en intervención separada

## riesgo residual

- la allowlist de egress sigue pendiente
- el runtime actual sigue usando el tag resuelto, aunque ya existe digest fijado para despliegues futuros
- UFW sigue con reglas históricas que conviene simplificar después, pero el drift crítico de persistencia ya quedó corregido
