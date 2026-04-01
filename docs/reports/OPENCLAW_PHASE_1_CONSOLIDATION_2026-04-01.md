# OpenClaw Phase 1 Consolidation 2026-04-01

## alcance

Cerrar la Fase 1 de consolidación de la zona de agentes como trust boundary operativa, sin introducir nuevas features y sin tocar `main`.

Fuera de alcance:

- broker restringido
- policy store
- menú de capacidades
- Telegram
- chat web
- nuevas automatizaciones
- cambios sobre Verity, `n8n`, NPM, WireGuard o PostgreSQL

## estado actual consolidado

### OpenClaw

- runtime real bajo `/opt/automation/agents/openclaw`
- servicio desplegado `openclaw-gateway`
- bind publicado solo por `127.0.0.1:18789`
- red separada `agents_net`
- mounts operativos:
  - `/workspace/config` readonly
  - `/workspace/state` read-write
  - `/workspace/logs` read-write
  - `/run/secrets/openclaw` readonly
- hardening base:
  - `no-new-privileges`
  - `cap_drop: ALL`

### inference-gateway

- runtime real bajo `/opt/automation/inference-gateway`
- gestionado por `systemd`
- bind permitido:
  - `127.0.0.1:11440`
  - `172.22.0.1:11440`
- bind no permitido:
  - IP pública del host
- contrato northbound mínimo:
  - `GET /healthz`
  - `GET /v1/models`
  - `POST /v1/chat/completions`
- upstream fijo:
  - Ollama por `127.0.0.1:11434`

### boundary de red

- `agents_net` validada en `172.22.0.0/16`
- `openclaw-gateway -> 172.22.0.1:11440` revalidado
- exposición pública de `11440` cerrada

## contrato operativo de OpenClaw

### qué puede tocar

- su propio runtime bajo `/opt/automation/agents/openclaw`
- el bind local `127.0.0.1:18789`
- el boundary de inferencia `http://172.22.0.1:11440/v1`

### qué no puede tocar

- `n8n`
- NPM
- WireGuard
- PostgreSQL
- `verity_network`
- Ollama directo como contrato de aplicación
- Internet libre
- secretos reales dentro del repo o del workspace del agente

### dependencias explícitas

- Docker
- red `agents_net`
- `inference-gateway.service`
- Ollama local en host

## contrato operativo de inference-gateway

### por qué existe como trust boundary separada

- evita que OpenClaw quede acoplado a la API nativa de Ollama
- deja un northbound mínimo y estable
- permite endurecer bind, reachability y logging sin tocar el runtime del agente
- mantiene el backend LLM fuera del workspace del agente

### límites de seguridad

- no exposición por IP pública
- bind limitado a loopback y gateway del bridge Docker necesario
- logging mínimo sin payloads completos
- modelo permitido explícito

## decisiones de endurecimiento MVP

### healthcheck de OpenClaw

Decisión:

- mantener el healthcheck actual

Razón:

- el healthcheck actual valida el runtime autenticado del gateway
- es más útil para este MVP que un TCP check ciego
- no hay evidencia actual de falsos positivos que justifique tocar runtime sensible en esta fase

### estrategia de imagen

Decisión:

- mantener el runtime actual en el tag revisado `ghcr.io/openclaw/openclaw:2026.2.3`
- exigir digest revisado en el siguiente cambio deliberado de imagen

Razón:

- cambiar imagen en esta fase no aporta endurecimiento del boundary
- fijar ahora una narrativa clara evita rotaciones oportunistas
- el pin por digest queda formalizado como requisito del siguiente refresh de imagen

### política de `OPENCLAW_GATEWAY_TOKEN`

Decisión:

- mantenerlo en el `.env` root-owned del runtime en esta fase

Razón:

- sigue fuera del repo y fuera del workspace del agente
- migrarlo ahora a `/etc/davlos/secrets/openclaw` sería una intervención runtime sensible con beneficio marginal en este MVP local
- la ruta de secretos queda reservada y montada para fases posteriores con credenciales externas o auth adicional

### drift de UFW

Decisión:

- dejarlo formalizado como deuda operativa de Fase 1
- no abrir una refactorización de firewall en esta fase

Estado conocido:

- hubo divergencia entre reglas declaradas y reglas efectivas cargadas en runtime
- la reachability requerida quedó restaurada con una regla runtime mínima y estrecha

Implicación:

- el boundary actual está operativo
- sigue pendiente una normalización para persistencia y reboot safety

## cambios aplicados en repo

- `docs/AGENTS.md`
  - consolidado como contrato operativo único de la zona de agentes
- `docs/OPENCLAW_HOST_SECRETS_CONTRACT_MVP.md`
  - fijada la política actual de `OPENCLAW_GATEWAY_TOKEN`
- `runbooks/OPENCLAW_DEPLOY_MVP.md`
  - documentada la decisión de healthcheck, estrategia de imagen y deuda UFW

## riesgos residuales

- allowlist real de egress para `agents_net` todavía no aplicada
- imagen aún fijada por tag y no por digest operativo final
- drift de UFW pendiente de normalización
- el boundary actual sigue siendo MVP endurecido, no política final de ejecución restringida

## backlog inmediato para Fase 2

- introducir broker restringido como siguiente boundary lógico
- definir política de capacidades antes de exponer acciones de escritura
- normalizar persistencia de reglas host-side de `agents_net -> 172.22.0.1:11440`
- fijar imagen por digest en el siguiente refresh controlado
- decidir si aparecen secretos host-side adicionales cuando exista backend externo o auth adicional
- diseñar allowlist real de egress para `agents_net`

## decisión final

### decisión

`GO` para pasar a Fase 2.

### motivo

La zona de agentes queda consolidada como trust boundary operativa:

- contratos y límites explícitos
- separación clara entre OpenClaw e `inference-gateway`
- reachability interna validada
- exposición pública del gateway cerrada
- backlog de endurecimiento posterior acotado y documentado
