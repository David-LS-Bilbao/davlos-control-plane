# Rollback mínimo verificable listo para futura migración de n8n

## Estado
Preparado, pero no ejecutado.

## Backup base disponible
- `/opt/backups/n8n/2026-03-30_pre_migration_01/docker-compose.yaml`
- `/opt/backups/n8n/2026-03-30_pre_migration_01/n8n.env`
- `/opt/backups/n8n/2026-03-30_pre_migration_01/local-files.tar.gz`
- `/opt/backups/n8n/2026-03-30_pre_migration_01/root_n8n_data.tar.gz`
- `/opt/backups/n8n/2026-03-30_pre_migration_01/n8n_postgres.dump`
- `/opt/backups/n8n/2026-03-30_pre_migration_01/SHA256SUMS.txt`

## Dependencias activas confirmadas
- compose activo en `/root/docker-compose.yaml`
- env activo en `/root/n8n.env`
- bind mount activo `/root/local-files -> /files`
- volumen persistente `root_n8n_data`
- red `verity_network`
- publicación local `127.0.0.1:5678`
- configuración activa con variables `DB_*` de PostgreSQL

## Criterio de rollback
Si una futura migración fuera de `/root` falla, el rollback mínimo consistirá en:
1. restaurar `/root/docker-compose.yaml`
2. restaurar `/root/n8n.env`
3. restaurar `/root/local-files`
4. restaurar el volumen `root_n8n_data`
5. conservar o restaurar la conectividad con PostgreSQL según el estado de la intervención
6. volver a levantar n8n con la definición previa conocida
7. validar acceso por `127.0.0.1:5678` y flujo vía NPM

## Nota importante
Este documento no ejecuta rollback.
Solo deja preparado el punto de reversión mínimo con copia real ya generada.

## Siguiente paso recomendado
No migrar todavía.
Preparar una ventana controlada de intervención con:
- objetivo exacto
- duración estimada
- criterio de abortar
- criterio de éxito
- pasos de migración
- pasos de rollback
