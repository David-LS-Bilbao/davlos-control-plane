# Runbook MVP: inference gateway sobre Ollama local

## objetivo

Levantar un proxy HTTP mínimo delante de Ollama local para dar a OpenClaw un endpoint interno estable sin credenciales externas.

## runtime recomendado

- `/opt/automation/inference-gateway`

## despliegue real del MVP

- servicio `systemd`: `inference-gateway.service`
- entorno host-side: `/opt/automation/inference-gateway/host.env`
- proxy Python mínimo bajo `/opt/automation/inference-gateway`

## pasos de despliegue

1. Materializar `/opt/automation/inference-gateway/host.env` con:
   - `INFERENCE_BIND_HOST`
   - `INFERENCE_BIND_PORT`
   - `OLLAMA_UPSTREAM`
   - `ALLOWED_MODEL`
2. Instalar o actualizar `/etc/systemd/system/inference-gateway.service`.
3. Confirmar que Ollama local responde en `127.0.0.1:11434`.
4. Recargar `systemd` y arrancar:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now inference-gateway`
5. Validar:
   - `curl http://127.0.0.1:11440/healthz`
   - `curl http://127.0.0.1:11440/v1/models`
   - `curl -s http://127.0.0.1:11440/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen2.5:3b","messages":[{"role":"user","content":"ping"}]}'`
   - `curl http://172.22.0.1:11440/healthz`

## contrato northbound del gateway

Base URL efectiva para OpenClaw:

- `http://172.22.0.1:11440/v1`

Rutas expuestas por el gateway:

- `GET /healthz`
- `GET /v1/models`
- `POST /v1/chat/completions`

No se expone `POST /v1/responses` en este MVP.

## criterio de aceptación

- servicio host-side activo por `systemd`
- endpoint interno estable para OpenClaw en `172.22.0.1:11440/v1`
- sin secretos necesarios para el primer MVP local
- OpenClaw puede apuntar a `http://172.22.0.1:11440/v1` y no a Ollama directo
