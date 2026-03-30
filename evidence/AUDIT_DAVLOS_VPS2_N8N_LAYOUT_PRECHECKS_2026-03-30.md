# Auditoría operativa DAVLOS VPS 2

## 1. Resumen ejecutivo

Punto real del proyecto a fecha `2026-03-30`:

- El `control-plane` ya cumple su función como fuente documental mínima del VPS y ya no necesita más iteración documental profunda para desbloquear la siguiente fase.
- `n8n` sigue operativo y responde en `127.0.0.1:5678`, pero la auditoría técnica profunda de contenedor, mounts, red y volumen no puede completarse desde el usuario `devops` porque no tiene acceso al socket Docker ni a `/root`.
- La Fase 2 de layout está cerrada solo a nivel de diseño documental. No está cerrada a nivel operativo.
- Ya se puede pasar a preparar un pack de `prechecks ejecutables`, pero todavía no a una implantación o migración. El bloqueo principal es de acceso operativo y verificación técnica real, no de documentación.

Diagnóstico operativo:

- `control-plane`: suficiente para decidir.
- `n8n`: parcialmente conocido.
- `migración fuera de /root`: no lista todavía.
- siguiente fase correcta: `prechecks ejecutables + habilitación de acceso operativo de solo lectura`.

## 2. Estado real confirmado del repo control-plane

### Estado general del repo

Confirmado por comandos locales:

- ruta de trabajo real: `/opt/control-plane`
- usuario actual: `devops`
- remoto configurado:
  - `git@github.com:David-LS-Bilbao/davlos-control-plane.git`
- estado git actual:
  - hay cambios sin commit en `docs/examples/N8N_WORKFLOW_INVENTORY_REAL_PARTIAL_01.md`

### Estructura actual confirmada

Estructura real observada:

- `README.md`
- `docs/`
- `runbooks/`
- `inventory/`
- `evidence/`
- `templates/`
- `policies/`

### Documentos clave existentes

Documentos operativamente útiles:

- `inventory/INITIAL_INVENTORY.md`
- `evidence/FASE_1_CIERRE.md`
- `docs/ARCHITECTURE.md`
- `docs/LAYOUT_PHASE_2_PROPOSAL.md`
- `docs/N8N_FUNCTIONAL_DEPENDENCIES.md`
- `runbooks/N8N_MIGRATION_PREP.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`

Documentos auxiliares no críticos para la decisión inmediata:

- `templates/N8N_WORKFLOW_AND_INTEGRATION_INVENTORY_TEMPLATE.md`
- `docs/N8N_INVENTORY_CAPTURE_GUIDE.md`
- `docs/examples/N8N_WORKFLOW_INVENTORY_PILOT.md`
- `docs/examples/N8N_WORKFLOW_INVENTORY_REAL_PARTIAL_01.md`
- `docs/AGENTS.md`
- `docs/SECURITY.md`

### Alineación o desalineación documental

Confirmado:

- `ARCHITECTURE.md`, `LAYOUT_PHASE_2_PROPOSAL.md`, `N8N_FUNCTIONAL_DEPENDENCIES.md` y ambos runbooks de `n8n` están alineados en el punto central:
  - `n8n` sigue dependiente de `/root`
  - el objetivo es moverlo a `/opt/automation/n8n`
  - no debe migrarse todavía sin prechecks, backup y rollback

Desalineación detectada:

- `README.md` está atrasado respecto al estado real del repo:
  - sigue diciendo `Fase 1 iniciada`
  - el repositorio ya contiene trabajo claro de Fase 2 documental y preparación de `n8n`

### Duplicidades documentales

Duplicidades parciales detectadas:

- `ARCHITECTURE.md` y `LAYOUT_PHASE_2_PROPOSAL.md` se solapan en layout objetivo y mapeo actual -> objetivo.
- `N8N_FUNCTIONAL_DEPENDENCIES.md` y `N8N_MIGRATION_PREP.md` se solapan en dependencias conocidas, riesgos y faltantes.
- las plantillas y ejemplos de inventario ya aportan poco valor adicional inmediato para la prioridad operativa actual.

### Juicio operativo sobre el repo

Conclusión:

- el repo ya está listo para dejar de profundizar documentación genérica
- no está listo todavía para ejecutar migración
- sí está listo para pasar a:
  - prechecks técnicos ejecutables
  - contraste real de Docker/root
  - preparación técnica de backup/rollback

### Qué documentos sirven, sobran o deberían consolidarse

Mantener como fuente activa:

- `inventory/INITIAL_INVENTORY.md`
- `evidence/FASE_1_CIERRE.md`
- `docs/ARCHITECTURE.md`
- `docs/LAYOUT_PHASE_2_PROPOSAL.md`
- `runbooks/N8N_MIGRATION_PREP.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`

Congelar y no ampliar salvo necesidad inmediata:

- `docs/N8N_FUNCTIONAL_DEPENDENCIES.md`
- `templates/N8N_WORKFLOW_AND_INTEGRATION_INVENTORY_TEMPLATE.md`
- `docs/N8N_INVENTORY_CAPTURE_GUIDE.md`
- `docs/examples/*`

Consolidación recomendable más adelante, pero no bloqueante ahora:

- simplificar `ARCHITECTURE.md` + `LAYOUT_PHASE_2_PROPOSAL.md`
- convertir `N8N_FUNCTIONAL_DEPENDENCIES.md` + `N8N_MIGRATION_PREP.md` en un único pack operativo de prechecks

## 3. Estado real confirmado de n8n

### Confirmado hoy por evidencia técnica en vivo

- `n8n` responde localmente en `http://127.0.0.1:5678` con `HTTP/1.1 200 OK`
- el puerto `127.0.0.1:5678` está en escucha
- Nginx Proxy Manager responde localmente en `http://127.0.0.1:81` con `HTTP/1.1 200 OK`
- NPM publica `80:80`, `443:443` y `127.0.0.1:81:81` según su compose en `/opt/verity-stack/npm/docker-compose.yml`
- el servicio NPM usa la red Docker externa `verity_network` según su compose

### Confirmado por evidencia histórica del control-plane, pero no revalidado hoy vía Docker

- `n8n` depende de:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen Docker `root_n8n_data`
- `n8n` publica `127.0.0.1:5678->5678/tcp`
- el contenedor histórico documentado es `root-n8n-1`
- la red histórica documentada es `verity_network`
- el bind mount histórico documentado es `/root/local-files -> /files`
- la persistencia histórica documentada es:
  - `/var/lib/docker/volumes/root_n8n_data/_data -> /home/node/.n8n`

### Bloqueo real de verificación en vivo

Confirmado hoy:

- `devops` no pertenece al grupo `docker`
- el socket Docker es `root:docker` con permisos `srw-rw----`
- `sudo` requiere contraseña interactiva
- `/root/docker-compose.yaml`, `/root/n8n.env` y `/root/local-files` no son accesibles desde `devops`
- `/var/lib/docker/volumes/root_n8n_data` no es accesible desde `devops`

Conclusión:

- la auditoría actual no puede confirmar por inspección directa de Docker:
  - el compose activo exacto
  - los mounts activos exactos
  - la red real enlazada al contenedor
  - el volumen realmente montado
  - el tipo de base de datos real
  - el número real de workflows activos/inactivos en la instancia

### Base de datos de n8n

Clasificación:

- `probable`: SQLite
- `no confirmado`: PostgreSQL

Justificación:

- la persistencia histórica documentada apunta a `/home/node/.n8n`, lo que encaja con el patrón típico de SQLite de `n8n`
- no existe hoy, desde `devops`, acceso suficiente para confirmar si la instancia activa usa `database.sqlite` o una base externa

### Dependencia con NPM / proxy / acceso

Clasificación:

- `confirmado`: `n8n` escucha solo por loopback en `127.0.0.1:5678`
- `confirmado`: NPM está diseñado para publicar `80/443` y gestionar proxy en `verity_network`
- `probable`: el acceso operativo a `n8n` depende de NPM o de otro reverse proxy interno
- `no confirmado`: host/proxy rule concreta de NPM hacia `n8n`

## 4. Dependencias activas que afectan a una futura migración fuera de /root

### Confirmado

- `n8n` responde localmente en `127.0.0.1:5678`
- la topología actual publicada deja fuera de exposición directa el puerto de `n8n`
- la documentación histórica del control-plane fija como dependencias operativas:
  - `/root/docker-compose.yaml`
  - `/root/n8n.env`
  - `/root/local-files`
  - volumen `root_n8n_data`
- existe una dependencia probable de proxy/publicación a través de NPM

### Probable

- `verity_network` sigue siendo la red efectiva de `n8n`
- `/root/local-files` sigue siendo dependencia funcional real
- la persistencia efectiva sigue estando en `root_n8n_data`
- el acceso externo a `n8n` está gobernado por NPM

### No confirmado

- labels Docker reales del contenedor `n8n`
- restart policy real del contenedor
- variables de entorno efectivamente cargadas por la instancia activa
- tipo de base de datos exacto
- si hay integración directa con PostgreSQL, correo, mensajería o APIs externas desde la instancia activa
- si hay dependencias ocultas adicionales en `compose`, `env` o mounts

## 5. Inventario mínimo útil de n8n para decidir la siguiente fase

### Qué puede afirmarse hoy

#### Confirmado

- existe una instancia `n8n` operativa y accesible localmente por `127.0.0.1:5678`
- existe al menos un artefacto documental de workflow en staging:
  - `clawbot_staging_receiver.workflow.json`
- ese artefacto documenta:
  - webhook `POST`
  - path `clawbot/staging/proposals`
  - receptor de propuestas de Clawbot en staging
  - cabeceras `X-Clawbot-Token` y `X-Clawbot-Environment`
  - `active: false`

#### Probable

- existen o existirán workflows de tipo webhook en el entorno `n8n`
- puede existir al menos un workflow asociado a Clawbot en staging
- el inventario funcional mínimo de `n8n` para migración debería incluir:
  - webhooks
  - dependencia de archivos
  - integraciones entrantes críticas

#### No confirmado

- cuántos workflows hay hoy en la instancia activa
- cuántos están activos o inactivos
- si existen cron/scheduled workflows hoy
- si la instancia activa contiene exactamente el workflow `clawbot_staging_receiver`
- si `/root/local-files` está siendo usado por workflows actuales
- si existen dependencias externas críticas visibles desde la instancia activa

### Juicio operativo sobre inventario mínimo útil

No hace falta más arqueología documental.
Sí hace falta una sola ronda de inspección técnica de la instancia activa para cerrar:

- número de workflows activos/inactivos
- existencia de webhooks
- existencia de cron/schedules
- presencia o no de referencias a `/files`
- tipo de base de datos real

Sin eso, el inventario mínimo útil sigue incompleto para migración.

## 6. Prechecks técnicos que ya pueden definirse

### Prechecks que ya pueden definirse hoy

#### Prechecks del host y del repo

```bash
pwd
whoami
hostnamectl
git -C /opt/control-plane status --short
git -C /opt/control-plane log --oneline -n 15
find /opt/control-plane -maxdepth 3 -type f | sort
ss -lntp
curl -I --max-time 5 http://127.0.0.1:5678
curl -I --max-time 5 http://127.0.0.1:81
```

#### Prechecks de permisos y acceso operativo

```bash
groups
ls -l /var/run/docker.sock
sudo -n docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Interpretación:

- si `sudo -n` falla o `devops` no entra en grupo `docker`, no hay base suficiente para auditar/migrar `n8n` con seguridad

#### Prechecks de n8n que deben ejecutarse como root o con acceso a Docker

```bash
sudo -n docker inspect root-n8n-1
sudo -n docker volume inspect root_n8n_data
sudo -n docker network inspect verity_network
sudo -n ls -ld /root /root/docker-compose.yaml /root/n8n.env /root/local-files
sudo -n du -sh /root/local-files /var/lib/docker/volumes/root_n8n_data/_data
sudo -n sh -c 'grep -E "^[A-Z0-9_]+=" /root/n8n.env | cut -d= -f1 | sort -u'
sudo -n docker exec root-n8n-1 sh -lc 'test -f /home/node/.n8n/database.sqlite && echo SQLITE_PRESENT || echo SQLITE_NOT_FOUND'
```

#### Prechecks mínimos de inventario funcional

Los siguientes deben ejecutarse solo si el acceso Docker/root ya está resuelto:

```bash
sudo -n docker inspect root-n8n-1 --format '{{json .Mounts}}'
sudo -n docker inspect root-n8n-1 --format '{{json .NetworkSettings.Networks}}'
sudo -n docker inspect root-n8n-1 --format '{{json .Config.Env}}'
sudo -n find /root/local-files -maxdepth 2 -type f | head -n 50
```

### Backup mínimo real que ya puede definirse

Ya puede definirse a nivel operativo, aunque no ejecutarse todavía:

- copia fechada del compose activo de `n8n`
- copia fechada de `/root/n8n.env` en ubicación segura, sin entrar en Git
- copia fechada de `/root/local-files`
- backup consistente del volumen `root_n8n_data`
- checksum o verificación de tamaño/artefacto generado

### Rollback mínimo real que ya puede definirse

Ya puede definirse hoy como criterio:

- restaurar compose original
- restaurar `n8n.env` original
- restaurar `local-files`
- restaurar volumen de persistencia
- revalidar `127.0.0.1:5678`
- revalidar acceso esperado por proxy

### Smoke tests mínimos post-migración que ya pueden definirse

Ya pueden definirse:

- `curl -I` al endpoint local de `n8n`
- confirmación de arranque estable del contenedor
- confirmación de mounts esperados
- confirmación del volumen esperado
- presencia de workflows esperados
- verificación funcional mínima de webhooks críticos identificados

### Ruta objetivo recomendada

Sigue siendo razonable como objetivo:

- `/opt/automation/n8n`

Subrutas operativas recomendables cuando llegue el momento:

- `/opt/automation/n8n/compose/`
- `/opt/automation/n8n/env/`
- `/opt/automation/n8n/local-files/`
- persistencia Docker o bind persistente documentado fuera de `/root`

## 7. Información que todavía falta

Faltantes críticos antes de preparar implantación:

- acceso operativo real a Docker o sesión root de solo lectura
- compose activo exacto de `n8n`
- claves de entorno usadas por `n8n` sin exponer valores
- mounts activos reales del contenedor
- red real del contenedor
- volumen real montado por el contenedor
- tipo de base de datos exacto
- número de workflows activos/inactivos
- existencia real de webhooks activos
- existencia real de cron/scheduled workflows
- uso real de `/root/local-files`
- inventario mínimo de integraciones críticas de la instancia activa

## 8. Riesgos reales actuales

- riesgo estructural: `n8n` sigue atado a `/root`
- riesgo operativo: no hay acceso suficiente desde `devops` para auditar ni preparar la migración con garantías
- riesgo de falsa confianza: la documentación sugiere una estructura bastante clara, pero la capa Docker activa no está reconfirmada hoy
- riesgo funcional: `/root/local-files` puede seguir siendo una dependencia real y hoy no está verificada
- riesgo de backup incompleto: no hay evidencia actual de backup restaurable del volumen ni del entorno
- riesgo de proxy: `n8n` parece depender de publicación indirecta, pero la regla concreta no está verificada
- riesgo de inventario insuficiente: el único workflow documentado de forma clara está en staging y marcado `active: false`

## 9. Qué parte de Fase 2 está realmente cerrada y qué no

### Realmente cerrada

- definición documental del layout objetivo por zonas
- mapeo conceptual actual -> objetivo
- identificación de `n8n` como principal deuda estructural
- criterio de no mover producción todavía
- criterio de hacer la transición por servicio

### Solo cerrada en modo documental

- movimiento futuro de `n8n` a `/opt/automation/n8n`
- estrategia final de persistencia de `n8n`
- pack de prechecks ejecutables como procedimiento cerrado
- backup y rollback reales de `n8n`
- validación funcional real de workflows/integraciones activas
- desacoplamiento real de `/root`

### Directorios objetivo que ya pueden prepararse sin tocar producción

Se pueden preparar de forma inocua:

- `/opt/automation/`
- `/opt/automation/n8n/`
- `/opt/backups/`

Siempre que se haga:

- sin mover artefactos activos
- sin editar compose actual
- sin cambiar rutas en producción

### Movimientos que no deben hacerse todavía

- mover cualquier artefacto activo de `n8n`
- tocar `/root/n8n.env`
- mover `/root/local-files`
- intervenir el volumen `root_n8n_data`
- reconfigurar NPM para apuntar a otra ruta/stack
- asumir equivalencia entre artefactos documentados de staging y la instancia activa

## 10. Recomendación operativa exacta para el siguiente paso

Siguiente paso exacto recomendado:

1. habilitar una ventana corta de auditoría de solo lectura con acceso Docker/root
2. ejecutar el pack mínimo de prechecks técnicos
3. capturar evidencia en el control-plane
4. cerrar backup mínimo real y rollback mínimo real
5. solo entonces preparar implantación

Decisión operativa:

- `sí` a preparar ya el pack de prechecks ejecutables
- `no` a preparar todavía la implantación real

## 11. Comandos de evidencia utilizados

```bash
pwd
whoami
hostnamectl
git -C /opt/control-plane status --short
git -C /opt/control-plane log --oneline -n 15
git -C /opt/control-plane remote -v
find /opt/control-plane -maxdepth 3 -type f | sort
find /opt -maxdepth 2 -mindepth 1 -type d | sort
find /opt -type f \( -name '*.workflow.json' -o -name '*n8n*json' \) 2>/dev/null | sort
find /opt/verity-stack/staging/verity-news-staging/docs/clawbot -maxdepth 2 -type f | sort
ss -lntp
curl -I --max-time 5 http://127.0.0.1:5678
curl -I --max-time 5 http://127.0.0.1:81
groups
ls -l /var/run/docker.sock
stat /root/docker-compose.yaml
stat /root/n8n.env
stat /root/local-files
ls -ld /var/lib/docker/volumes/root_n8n_data /var/lib/docker/volumes/root_n8n_data/_data
du -sh /root/local-files
sed -n '1,220p' /opt/control-plane/README.md
sed -n '1,220p' /opt/control-plane/docs/ARCHITECTURE.md
sed -n '1,220p' /opt/control-plane/docs/LAYOUT_PHASE_2_PROPOSAL.md
sed -n '1,260p' /opt/control-plane/docs/N8N_FUNCTIONAL_DEPENDENCIES.md
sed -n '1,220p' /opt/control-plane/runbooks/N8N_MIGRATION_PREP.md
sed -n '1,220p' /opt/control-plane/runbooks/N8N_POST_MIGRATION_VALIDATION.md
sed -n '1,220p' /opt/control-plane/docs/SECURITY.md
sed -n '1,220p' /opt/control-plane/docs/AGENTS.md
sed -n '1,220p' /opt/verity-stack/npm/docker-compose.yml
sed -n '1,260p' /opt/verity-stack/staging/verity-news-staging/docker-compose.yml
sed -n '1,240p' /opt/verity-stack/staging/verity-news-staging/docs/clawbot/n8n-workflow-minimum-structure.md
sed -n '1,220p' /opt/verity-stack/staging/verity-news-staging/docs/clawbot/n8n-webhook-receiver-contract.md
sed -n '1,220p' /opt/verity-stack/staging/verity-news-staging/docs/clawbot/clawbot-integration-contract.md
sed -n '1,240p' /opt/verity-stack/staging/verity-news-staging/docs/clawbot/clawbot_staging_receiver.workflow.json
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker inspect root-n8n-1
docker volume inspect root_n8n_data
docker network inspect verity_network
sudo docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
sudo docker inspect root-n8n-1
sudo docker volume inspect root_n8n_data
sudo docker network inspect verity_network
```

Nota sobre los comandos fallidos:

- los comandos Docker y acceso a `/root` fallaron por permisos del usuario actual; ese fallo es en sí mismo un hallazgo operativo relevante

## 12. Anexo: clasificación de hallazgos (confirmado / probable / no confirmado)

| Hallazgo | Clasificación | Base |
|---|---|---|
| El control-plane existe y está versionado en `/opt/control-plane` | Confirmado | repo local y git |
| El repo ya está en Fase 2 documental, no solo Fase 1 | Confirmado | historial git y documentos actuales |
| `README.md` está atrasado | Confirmado | lectura directa |
| `n8n` responde en `127.0.0.1:5678` | Confirmado | `ss` + `curl -I` |
| NPM responde en `127.0.0.1:81` y publica `80/443` | Confirmado | `curl -I` + compose NPM |
| `n8n` sigue dependiendo de `/root` hoy mismo | Probable | evidencia histórica fuerte, no revalidada hoy por Docker/root |
| `root_n8n_data` sigue siendo el volumen real de la instancia activa | Probable | evidencia histórica fuerte, no revalidada hoy por Docker |
| `/root/local-files` sigue siendo dependencia funcional real | Probable | evidencia histórica fuerte, no revalidada hoy por lectura directa |
| `verity_network` sigue siendo la red real de `n8n` | Probable | evidencia histórica fuerte + NPM usa esa red |
| El acceso externo a `n8n` depende de NPM | Probable | topología de puertos y diseño de NPM |
| `n8n` usa SQLite | Probable | patrón típico de persistencia en `/home/node/.n8n`, no verificado hoy |
| El workflow `clawbot_staging_receiver` está activo en la instancia actual | No confirmado | solo existe artefacto documental con `active: false` |
| Existen cron/scheduled workflows activos en la instancia | No confirmado | sin acceso a Docker/DB |
| Existen webhooks activos en la instancia | No confirmado | hay artefacto documental, pero no verificación sobre la instancia activa |
| `/root/local-files` no se usa realmente | No confirmado | falta inspección directa |
| Ya estamos listos para implantación | No confirmado | faltan prechecks técnicos reales y acceso operativo |
