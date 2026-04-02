# Inference gateway MVP sobre Ollama local

## decisión aplicada

La opción aplicada en este VPS es un **gateway HTTP mínimo en host**, gestionado por `systemd`, que habla con Ollama por loopback y expone un endpoint interno estable para OpenClaw.

Topología efectiva:

- gateway en host -> `127.0.0.1:11434`
- OpenClaw en `agents_net` -> `http://172.22.0.1:11440/v1`

Rutas de validación desde host:

- `http://127.0.0.1:11440`
- `http://172.22.0.1:11440`

## por qué se eligió así

- suficientemente ligera para un VPS modesto
- más simple y estable que pelear con `gateway(container) -> ollama(host)`
- mantiene un endpoint estable para OpenClaw sin acoplarlo a la API nativa de Ollama
- evita introducir credenciales externas en el primer arranque
- mantiene el cambio reversible y con radio de impacto bajo

## alternativas descartadas

### 1. OpenClaw -> Ollama directo

Se descarta para el MVP porque:

- no crea trust boundary clara
- no fija un endpoint estable independiente del backend
- no deja sitio limpio para política/logging/allowlist

### 2. Proxy contenedorizado sobre `agents_net`

Se descartó para este tramo porque:

- añadía fricción innecesaria entre contenedor y host
- el camino más estable ya era gateway en host -> Ollama en loopback
- OpenClaw puede alcanzar el host por la IP de gateway del bridge Docker

## contrato mínimo del endpoint interno

Base URL:

- para OpenClaw: `http://172.22.0.1:11440/v1`
- para validación desde host: `http://127.0.0.1:11440`
- para validación desde el bridge Docker: `http://172.22.0.1:11440`

Rutas mínimas previstas:

- `GET /healthz`
  - salud simple del proxy
- `GET /v1/models`
  - listado northbound estable y filtrado por el modelo permitido
- `POST /v1/chat/completions`
  - contrato mínimo northbound para conversación

No se incluye `POST /v1/responses` en el MVP:

- añade superficie API sin necesidad inmediata
- obliga a fijar semánticas extra que hoy no necesitamos para el primer arranque
- puede añadirse después sin romper la base `GET /healthz` + `GET /v1/models` + `POST /v1/chat/completions`

## traducción hacia Ollama

El gateway expone una API northbound mínima y estable, y traduce internamente a Ollama:

- `GET /v1/models` -> `GET /api/tags`
- `POST /v1/chat/completions` -> `POST /api/chat`

La respuesta northbound se normaliza en formato interno tipo OpenAI-compatible mínimo para evitar acoplar OpenClaw a `/api/chat` o `/api/generate`.

## política MVP del proxy

- servicio host-side gestionado por `systemd`
- bind en host para exponer `11440` al bridge Docker
- upstream fijo a Ollama local vía `127.0.0.1:11434`
- modelo permitido por defecto: `qwen2.5:3b`
- logging mínimo sin payloads completos
- sin secretos necesarios en este primer MVP local

## dónde debe vivir

Runtime recomendado:

- runtime materializado bajo `/opt/automation/inference-gateway`
- `host.env` bajo ese runtime
- unidad `systemd` en `/etc/systemd/system/inference-gateway.service`

Motivo:

- es un servicio compartido, no parte del sandbox de OpenClaw
- debe quedar fuera del workspace del agente
- encaja mejor como trust boundary separada
- sigue siendo ligero aunque viva en host

## estado operativo esperado

- `GET /healthz` correcto en `127.0.0.1:11440`
- `GET /v1/models` correcto en `127.0.0.1:11440`
- `POST /v1/chat/completions` correcto en `127.0.0.1:11440`
- `GET /healthz` correcto en `172.22.0.1:11440`
- OpenClaw consumiendo `http://172.22.0.1:11440/v1`
