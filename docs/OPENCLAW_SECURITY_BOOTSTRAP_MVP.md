# OpenClaw security bootstrap MVP

## objetivo

Dejar fijado el bootstrap mínimo de seguridad que ha permitido el primer arranque real de OpenClaw sin tocar el resto del VPS.

## diagnóstico corto

El MVP quedó cerrado con estas decisiones:

- `openclaw.json` mínimo confirmado para la imagen elegida
- inferencia local a través de `inference-gateway` en host
- bind host de OpenClaw solo por `127.0.0.1:18789`
- red dedicada `agents_net`
- sin credenciales cloud en este primer MVP local

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
- acceso controlado al backend de inferencia aprobado en `172.22.0.1:11440`
- DNS y HTTPS solo cuando se implemente la allowlist real

### prohibido por defecto

- exposición pública directa
- acceso libre a Internet
- acceso a `verity_network`
- acceso implícito al host, `n8n`, NPM, WireGuard o PostgreSQL
- uso de credenciales externas dentro del workspace del agente

## contrato base de `openclaw.json`

El runtime usa `/workspace/config/openclaw.json` con un contrato mínimo suficiente para el MVP:

- gateway local en `18789`
- auth por token local de gateway
- proveedor `davlos-local`
- endpoint de inferencia `http://172.22.0.1:11440/v1`
- modelo `qwen2.5:3b`

## qué debe quedar listo tras este tramo

- contrato mínimo de `openclaw.json`
- contrato host-side de secretos documentado
- política mínima de inferencia cerrada
- política MVP de red/egress documentada

## qué queda pendiente después del primer arranque

- decidir si se mantiene la versión fijada o se cambia a pin por digest
- endurecer el healthcheck si el TCP check deja de bastar
- introducir secretos host-side solo si aparece un backend externo o auth adicional
- ejecutar pruebas funcionales sobre el runtime ya desplegado
