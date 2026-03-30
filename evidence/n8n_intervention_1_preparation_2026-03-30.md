# Intervención 1 — preparación sin impacto

## 1. Objetivo

Preparar la futura migración de `n8n` fuera de `/root` hacia el layout objetivo sin activar ningún cambio en producción.

Objetivo concreto de esta intervención:

- preparar la estructura objetivo bajo `/opt/automation/n8n`
- dejar listo un compose objetivo de trabajo
- dejar referencias seguras al estado actual
- no detener `n8n`
- no recrear contenedores
- no tocar NPM
- no mover artefactos activos bajo `/root`

## 2. Estado previo confirmado

Estado confirmado en runtime y runbooks:

- `n8n` sigue dependiendo de:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`
  - red Docker `verity_network`
- `n8n` está expuesto en `127.0.0.1:5678`
- NPM sigue detrás de la topología actual
- el contenedor actual observado es `root-n8n-1`
- imagen observada:
  - `docker.n8n.io/n8nio/n8n`
- restart policy observada:
  - `unless-stopped`
- bind mount observado:
  - `/root/local-files -> /files`
- persistencia observada:
  - `root_n8n_data -> /home/node/.n8n`
- el helper readonly sigue funcionando
- existe backup mínimo real en:
  - `/opt/backups/n8n/2026-03-30_pre_migration_01`

## 3. Directorios preparados

Resultado real actualizado:

- la estructura objetivo base sí existe ya bajo `/opt/automation/n8n`

Directorios confirmados:

- `/opt/automation`
- `/opt/automation/n8n`
- `/opt/automation/n8n/compose`
- `/opt/automation/n8n/env`
- `/opt/automation/n8n/local-files`
- `/opt/automation/n8n/docs`

Permisos observados:

- `/opt/automation` y subdirectorios generales:
  - `root:root` con modo `0755`
- `/opt/automation/n8n/local-files`:
  - `root:root` con modo `0700`

Interpretación:

- la subfase root de filesystem quedó materialmente creada
- la ruta de trabajo quedó preparada
- la zona `local-files` quedó más restringida, lo cual protege contenido pero limita verificación desde `devops`

## 4. Artefactos preparados

Preparados en esta intervención:

- referencia runtime confirmada del servicio actual
- referencia runtime confirmada de red, puerto, volumen y bind mount
- estructura objetivo base creada bajo `/opt/automation/n8n`
- presencia confirmada de:
  - `/opt/automation/n8n/compose/docker-compose.yaml`
  - `/opt/automation/n8n/env/n8n.env`
- compose objetivo de trabajo documentado en este informe

Bloqueo residual observado:

- el compose copiado y el env copiado están en:
  - `root:root`
  - modo `0600`
- desde `devops` no pueden leerse ni ajustarse
- `local-files` existe, pero su contenido no es visible desde `devops` por modo `0700`
- por tanto no fue posible completar desde esta sesión la preparación material del compose objetivo de trabajo dentro de `/opt/automation/n8n/compose/`

Nota documental mínima sobre el bind mount actual:

- estado actual confirmado:
  - `/root/local-files -> /files`
- estado objetivo deseado para la futura ventana:
  - `/opt/automation/n8n/local-files -> /files`

## 5. Compose objetivo de trabajo

Compose objetivo de trabajo propuesto para la futura ventana real.

Estado:

- preparado a nivel documental
- no ejecutado
- no materializado todavía dentro de `/opt/automation/n8n/compose/docker-compose.yaml` por falta de acceso de lectura/escritura a ese archivo desde `devops`
- no validado todavía contra el compose original línea por línea
- diseñado para mantener la misma topología confirmada

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n
    restart: unless-stopped
    ports:
      - "127.0.0.1:5678:5678"
    env_file:
      - ../env/n8n.env
    volumes:
      - root_n8n_data:/home/node/.n8n
      - ../local-files:/files
    networks:
      - verity_network

volumes:
  root_n8n_data:
    external: true

networks:
  verity_network:
    external: true
```

Observaciones prudentes:

- se mantiene el volumen actual `root_n8n_data` para reducir riesgo
- se mantiene `verity_network` como red externa
- se mantiene `127.0.0.1:5678`
- no se introducen valores de entorno en el compose
- antes de una futura ejecución debe contrastarse este compose de trabajo contra el compose real activo para detectar cualquier parámetro adicional no recogido aquí

## 6. Qué sigue intacto en producción

Sigue completamente intacto:

- contenedor actual de `n8n`
- NPM
- puerto `127.0.0.1:5678`
- `/root/docker-compose.yaml`
- `/root/n8n.env`
- `/root/local-files`
- volumen `root_n8n_data`
- red `verity_network`

No se ha hecho:

- ningún `down`
- ningún `up`
- ningún `restart`
- ninguna copia desde `/root`
- ningún cambio en secretos
- ningún cambio en proxy
- ningún cambio en el compose activo de `/root`

## 7. Riesgos

- el bloqueo actual ya no es de diseño, sino de permisos sobre la zona de preparación ya creada bajo `/opt/automation/n8n`
- el compose objetivo de trabajo es correcto a nivel topológico, pero todavía debe materializarse y contrastarse contra el compose real copiado antes de usarlo
- la zona `local-files` quedó protegida con permisos que impiden verificación desde `devops`
- el env copiado existe, pero su revisión debe seguir tratándose con precaución para no exponer valores

## 8. Siguiente paso para Intervención 2

Antes de la futura ventana corta de cambio real, hace falta una subfase previa mínima de root controlado sobre la zona ya creada:

1. confirmar con root que:
   - `local-files` fue copiado completo
   - `compose` copiado corresponde al activo
   - `env` copiado corresponde al activo
2. ajustar ownership/permisos de la zona de preparación para permitir revisión controlada:
   - como mínimo del compose de trabajo
   - sin abrir exposición innecesaria del env
3. guardar el compose objetivo revisado en `/opt/automation/n8n/compose/docker-compose.yaml`
4. solo entonces abrir la ventana real de cambio descrita en:
   - `runbooks/N8N_MIGRATION_WINDOW_PLAN.md`

Resultado operativo de esta Intervención 1:

- preparación material base completada
- preparación técnica final del compose objetivo de trabajo todavía parcial por permisos
