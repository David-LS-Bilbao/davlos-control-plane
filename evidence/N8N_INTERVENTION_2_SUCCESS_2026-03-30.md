# Intervención 2 — éxito de migración operativa

## fecha

2026-03-30

## resultado: PASS

PASS

## qué quedó operativo

- `n8n` depende operativamente de `/opt/automation/n8n/compose/docker-compose.yaml`
- `n8n` depende operativamente de `/opt/automation/n8n/env/n8n.env`
- `n8n` depende operativamente de `/opt/automation/n8n/local-files`
- se mantiene `127.0.0.1:5678`
- se mantiene `verity_network`
- se mantiene `root_n8n_data`
- se mantiene el acceso detrás de NPM

## qué quedó intacto

- `127.0.0.1:5678`
- `127.0.0.1:81`
- `verity_network`
- `root_n8n_data`
- en esta fase no se borran artefactos bajo `/root`

## deuda residual

- artefactos históricos aún presentes bajo `/root`
- nombre histórico del volumen `root_n8n_data`
- rotación posterior de secretos expuestos en chat

## siguiente paso exacto

- cerrar Fase 3 sin borrar todavía artefactos bajo `/root`
