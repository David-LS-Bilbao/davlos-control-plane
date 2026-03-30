# Ejecución runtime del helper readonly para auditoría n8n

## Resumen
Se ha validado con éxito el helper root-owned `davlos-n8n-audit-readonly` en modo lectura.

## Hallazgos confirmados
- Contenedor activo: `root-n8n-1`
- Puerto publicado: `127.0.0.1:5678`
- Volumen persistente: `root_n8n_data -> /home/node/.n8n`
- Bind mount activo: `/root/local-files -> /files`
- Red Docker: `verity_network`
- Variables de entorno presentes para backend PostgreSQL:
  - `DB_TYPE`
  - `DB_POSTGRESDB_HOST`
  - `DB_POSTGRESDB_PORT`
  - `DB_POSTGRESDB_DATABASE`
  - `DB_POSTGRESDB_USER`
  - `DB_POSTGRESDB_PASSWORD`
- `inventory_minimum` confirma:
  - `SQLITE_PRESENT`
  - 3 ficheros detectados en `local-files`
  - uso en disco de `/root/local-files`: `80K`

## Interpretación operativa
La presencia de `database.sqlite` en `/home/node/.n8n` se considera un artefacto persistente histórico y no prueba por sí sola que SQLite siga siendo el backend activo.
La evidencia en vivo de variables `DB_*` y el estado previo documentado apuntan a PostgreSQL como backend operativo actual.

## Conclusión
La auditoría readonly queda cerrada funcionalmente mediante helper restringido.
Se confirma que n8n sigue dependiendo estructuralmente de:
- Docker
- `/root/local-files`
- volumen `root_n8n_data`
- red `verity_network`

## Siguiente paso recomendado
No adaptar todavía los scripts 30 y 40.
Pasar a preparar:
1. backup real mínimo
2. checklist de rollback mínimo
3. criterio de ventana de intervención para futura migración fuera de `/root`
