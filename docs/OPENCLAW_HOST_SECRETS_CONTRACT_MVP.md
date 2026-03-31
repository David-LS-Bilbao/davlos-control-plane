# OpenClaw host-side secrets contract MVP

## objetivo

Definir qué tipos de secretos deben vivir en `/etc/davlos/secrets/openclaw`, sin poner valores reales en el repo y sin acoplarlos al workspace del agente.

## regla base

Los secretos viven en host-side bajo:

- `/etc/davlos/secrets/openclaw`

No deben vivir en:

- `openclaw.env.example`
- `openclaw.json`
- el workspace del agente
- el repositorio `control-plane`

## estado real del MVP local

En el MVP local actualmente desplegado:

- `/etc/davlos/secrets/openclaw` puede permanecer vacío
- no hay `provider_api_key`
- no hay token de proveedor externo
- el único secreto operativo mínimo es `OPENCLAW_GATEWAY_TOKEN`
- ese token vive en `/opt/automation/agents/openclaw/compose/.env`, fuera del repo y fuera del workspace del agente

## tipos de secretos que siguen reservados para fases posteriores

### 1. credencial de backend de inferencia externo

Solo si en el futuro se usa un proveedor externo.

Ejemplos de tipo:

- API key de proveedor LLM
- token de acceso a un inference gateway externo

### 2. token o secreto adicional del gateway interno

Solo si una fase posterior introduce auth adicional entre OpenClaw y el gateway.

Ejemplos de tipo:

- bearer token interno
- shared secret de routing

### 3. secreto de sesión o autenticación del propio runtime

Solo si la imagen/config real de OpenClaw lo exige más allá del token local actual.

Ejemplos de tipo:

- session secret
- signing secret
- auth token del runtime

## nombres de archivo sugeridos

Estos nombres son de contrato host-side sugerido, no de sintaxis obligatoria del producto:

- `provider_api_key`
- `inference_gateway_token`
- `runtime_session_secret`

## estado recomendado para el primer arranque

Si el primer arranque usa backend local sin credenciales externas:

- puede no ser necesario `provider_api_key`
- la ruta de secretos debe seguir existiendo igualmente
- el contrato queda listo para crecer sin reestructurar el runtime
- `OPENCLAW_GATEWAY_TOKEN` puede vivir en el `.env` real del runtime mientras siga siendo un MVP local sin proveedor externo

## pendiente antes del deploy

- decidir si el token local del gateway debe migrar a `/etc/davlos/secrets/openclaw`
- decidir qué nombres finales de archivos se usarán en `/run/secrets/openclaw` si aparecen secretos reales adicionales
