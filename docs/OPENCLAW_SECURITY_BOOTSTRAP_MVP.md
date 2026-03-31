# OpenClaw security bootstrap MVP

## objetivo

Dejar definido el bootstrap mínimo de seguridad antes del primer arranque real de OpenClaw, sin desplegar todavía nada.

## diagnóstico corto

El scaffold base ya existe, pero el matiz de seguridad que faltaba era este:

- el runtime tiene rutas, compose y `.env`, pero aún no tiene contrato claro de `openclaw.json`
- la ruta de secretos existe, pero no está definido qué tipos de secretos vivirán ahí
- no está cerrada la estrategia de inferencia para el primer arranque
- no está cerrada la política mínima de red/egress previa al deploy

## decisión recomendada para el primer arranque

Recomendación:

- primer arranque con **backend local sin credenciales externas directas**
- preferencia por **Ollama local** como backend inicial
- preferencia por exponerlo a OpenClaw **a través de un gateway/proxy interno simple** en el siguiente tramo, en lugar de permitir que el agente hable “a pelo” con credenciales o con endpoints externos

## por qué

- evita meter API keys externas en el primer arranque
- reduce superficie de fuga desde un sandbox que debe tratarse como potencialmente hostil
- permite empezar con una topología local y reversible
- deja preparado el paso siguiente hacia `inference.local` o un privacy router simple sin inventar que ya existe

## política MVP de red / egress

### permitido

- bind local del gateway en `127.0.0.1:18789`
- red dedicada `agents_net` para el contenedor
- acceso futuro y controlado al backend de inferencia que se apruebe
- DNS y HTTPS solo cuando se implemente la allowlist real

### prohibido por defecto

- exposición pública directa
- acceso libre a Internet
- acceso a `verity_network`
- acceso implícito al host, `n8n`, NPM, WireGuard o PostgreSQL
- uso de credenciales externas dentro del workspace del agente

## contrato base de `openclaw.json`

El template de compose apunta a `/workspace/config/openclaw.json`, pero el repo no contiene todavía un esquema confirmado del runtime real.

Por tanto, en este tramo:

- se define un **contrato bootstrap** en `templates/openclaw/openclaw.json.example`
- ese archivo **no debe tratarse todavía como configuración validada de producción**
- sirve para fijar:
  - puerto esperado
  - rutas de estado/log
  - estrategia de inferencia
  - separación entre configuración no sensible y secretos host-side

## qué debe quedar listo tras este tramo

- contrato bootstrap de `openclaw.json`
- contrato host-side de secretos
- política mínima de inferencia
- política MVP de red/egress documentada

## qué sigue pendiente antes de `docker compose up`

- confirmar sintaxis/config real soportada por la imagen elegida
- decidir imagen definitiva de OpenClaw
- materializar secretos reales en `/etc/davlos/secrets/openclaw`
- decidir el endpoint interno real de inferencia
- validar predeploy del runtime ya con imagen y secretos
