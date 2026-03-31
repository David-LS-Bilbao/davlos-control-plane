# Runbook MVP: rollback de OpenClaw

## objetivo

Retirar el despliegue de OpenClaw sin afectar al resto del VPS.

## pasos

1. Parar el compose de OpenClaw.
2. Confirmar que no quedan contenedores `openclaw` en ejecución.
3. Mantener `state` y `logs` para análisis.
4. Retirar `agents_net` solo si no está en uso.
5. Confirmar que `n8n`, NPM y WireGuard siguen intactos.

## no hacer

- no borrar secretos sin revisión
- no borrar evidencia o logs de validación
- no tocar `verity_network`
