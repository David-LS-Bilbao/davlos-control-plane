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

## tipos mínimos de secretos previstos

### 1. credencial de backend de inferencia externo

Solo si en el futuro se usa un proveedor externo.

Ejemplos de tipo:

- API key de proveedor LLM
- token de acceso a un inference gateway externo

### 2. token o secreto del gateway interno

Solo si el siguiente tramo introduce un proxy/gateway interno entre OpenClaw y el backend de inferencia.

Ejemplos de tipo:

- bearer token interno
- shared secret de routing

### 3. secreto de sesión o autenticación del propio runtime

Solo si la imagen/config real de OpenClaw lo exige.

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

## pendiente antes del deploy

- confirmar qué secretos exige la imagen real
- confirmar si habrá gateway interno en el siguiente tramo
- decidir qué nombres finales de archivos se usarán en `/run/secrets/openclaw`
