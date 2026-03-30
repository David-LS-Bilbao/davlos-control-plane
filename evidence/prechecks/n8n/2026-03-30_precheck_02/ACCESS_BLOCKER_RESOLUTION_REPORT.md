# Resolución del bloqueo de acceso para auditoría n8n

## 1. Resumen

Estado de esta tarea: `PARTIAL`.

El bloqueo de acceso ha quedado auditado con evidencia suficiente.
No se ha aplicado ningún cambio de privilegios en el sistema porque no existe, desde la sesión actual de `devops`, una vía segura y verificable para implantarlo sin credenciales root o sin abrir privilegios más amplios de lo necesario.

Conclusión operativa:

- el bloqueo exacto está identificado
- la opción más segura está definida
- la implantación debe ejecutarla un operador con root
- no se ha reintentado `30_n8n_docker_readonly.sh` ni `40_n8n_inventory_minimum.sh` porque no ha habido cambio efectivo de acceso

## 2. Bloqueo exacto detectado

Evidencia confirmada:

- `id`:
  - `uid=1000(devops) gid=1000(devops) groups=1000(devops),27(sudo),100(users),988(ollama)`
- `groups`:
  - `devops sudo users ollama`
- `sudo -n -l`:
  - requiere contraseña
- socket Docker:
  - `/var/run/docker.sock` es `root:docker` con permisos `srw-rw----`
- `/root`:
  - `drwx------ root root`
- acceso a:
  - `/root/docker-compose.yaml`: bloqueado
  - `/root/n8n.env`: bloqueado
  - `/root/local-files`: bloqueado

Consecuencia:

- `devops` no puede usar Docker en modo lectura
- `devops` no puede inspeccionar artefactos bajo `/root`
- `sudo -n` no permite resolver el bloqueo sin interacción

## 3. Opciones evaluadas

### Opción A: ejecutar los scripts 30 y 40 con `sudo` controlado

Ventaja:

- simple en apariencia

Problema de seguridad:

- los scripts actuales viven en `/opt/control-plane/scripts/...`
- esa ruta es editable por `devops`
- permitir en sudoers la ejecución directa de scripts editables por el mismo usuario equivale a abrir una vía de escalada

Veredicto:

- descartada como opción recomendada

### Opción B: helper root-owned readonly + sudoers restringido

Descripción:

- crear un helper fuera del repo, por ejemplo:
  - `/usr/local/sbin/davlos-n8n-audit-readonly`
- propiedad:
  - `root:root`
- permisos:
  - `0750`
- permitir por sudoers solo subcomandos concretos y no interactivos

Ventajas:

- mínimo privilegio
- auditable
- reversible
- no concede acceso general a Docker
- no concede acceso general a `/root`
- evita ejecutar con sudo scripts editables por `devops`

Veredicto:

- opción recomendada

### Opción C: añadir `devops` al grupo `docker`

Ventaja:

- resolvería rápido el acceso a Docker

Problema de seguridad:

- pertenecer al grupo `docker` equivale en la práctica a acceso casi root sobre el host
- rompe el objetivo de mínimo privilegio
- no resuelve por sí solo el acceso a `/root`

Veredicto:

- descartada salvo última opción y con aprobación explícita

## 4. Opción recomendada

Opción recomendada: `B`.

Razón:

- es la opción más prudente que permite auditoría real sin abrir privilegios operativos generales
- el alcance puede limitarse exactamente a lo que necesitan los prechecks bloqueados
- el cambio es reversible eliminando helper y sudoers

## 5. Cambios aplicados o procedimiento manual propuesto

### Cambios aplicados

- no se ha aplicado ningún cambio de privilegios
- se ha documentado el bloqueo y se ha dejado evidencia en esta carpeta

### Procedimiento manual propuesto

Debe ejecutarlo un operador con root.

#### Paso 1. Crear helper root-owned

Ruta recomendada:

- `/usr/local/sbin/davlos-n8n-audit-readonly`

El helper debe aceptar solo dos subcomandos:

- `docker_readonly`
- `inventory_minimum`

Contenido funcional esperado del helper:

- `docker_readonly`
  - `docker inspect root-n8n-1` con salida filtrada a:
    - imagen
    - estado
    - restart policy
    - mounts
    - redes
    - port bindings
    - claves de entorno, nunca valores
  - `docker volume inspect root_n8n_data`
  - `docker network inspect verity_network`

- `inventory_minimum`
  - comprobar presencia de `/home/node/.n8n/database.sqlite` dentro del contenedor
  - contar archivos de primer/segundo nivel en `/root/local-files`
  - `du -sh /root/local-files`
  - no exportar workflows
  - no imprimir secretos
  - no imprimir valores de variables

Permisos:

```bash
sudo install -o root -g root -m 0750 /tmp/davlos-n8n-audit-readonly /usr/local/sbin/davlos-n8n-audit-readonly
```

#### Paso 2. Crear sudoers restringido

Archivo recomendado:

- `/etc/sudoers.d/davlos-n8n-audit-readonly`

Contenido recomendado:

```sudoers
Cmnd_Alias DAVLOS_N8N_AUDIT = /usr/local/sbin/davlos-n8n-audit-readonly docker_readonly, /usr/local/sbin/davlos-n8n-audit-readonly inventory_minimum
devops ALL=(root) NOPASSWD: DAVLOS_N8N_AUDIT
```

Validación:

```bash
sudo visudo -cf /etc/sudoers.d/davlos-n8n-audit-readonly
```

#### Paso 3. Reintento de auditoría

Tras aplicar el helper:

```bash
sudo -n /usr/local/sbin/davlos-n8n-audit-readonly docker_readonly
sudo -n /usr/local/sbin/davlos-n8n-audit-readonly inventory_minimum
```

#### Paso 4. Adaptación controlada del pack

La opción más limpia es:

- no dar sudo directo a los scripts actuales
- adaptar más adelante `30_n8n_docker_readonly.sh` y `40_n8n_inventory_minimum.sh` para que llamen al helper si detectan este modo restringido

## 6. Riesgos de seguridad

Riesgos de una mala solución:

- permitir sudo sobre scripts editables por `devops`
- meter `devops` en `docker`
- exponer variables de entorno o secretos en salidas de auditoría
- dar acceso general a `/root`

Riesgos residuales de la opción recomendada:

- el helper debe revisarse cuidadosamente para que no ejecute nada fuera de lectura
- el sudoers debe limitarse a rutas exactas y subcomandos exactos
- cualquier cambio futuro en el helper debe hacerlo root, no `devops`

## 7. Rollback

Rollback de la opción recomendada:

```bash
sudo rm -f /etc/sudoers.d/davlos-n8n-audit-readonly
sudo rm -f /usr/local/sbin/davlos-n8n-audit-readonly
sudo visudo -c
```

Resultado esperado:

- `devops` vuelve al estado previo sin acceso adicional

## 8. Resultado del reintento de scripts 30 y 40

No hubo reintento efectivo.

Motivo:

- no se aplicó ningún cambio seguro de acceso
- repetir los scripts sin resolver el bloqueo solo reproduciría el mismo fallo

Estado:

- `30_n8n_docker_readonly.sh`: no reintentado
- `40_n8n_inventory_minimum.sh`: no reintentado

## 9. Estado final: PASS / PARTIAL / BLOCKED

Estado final: `PARTIAL`.

Interpretación:

- el bloqueo está resuelto a nivel de diseño operativo
- no está resuelto todavía a nivel de acceso aplicado en el host

## 10. Siguiente paso exacto

Siguiente paso exacto recomendado:

1. un operador con root crea el helper root-owned readonly
2. ese operador instala el sudoers restringido
3. se valida con `sudo -n -l` desde `devops`
4. se reintentan solo:
   - `30_n8n_docker_readonly.sh`
   - `40_n8n_inventory_minimum.sh`
5. si ambos cierran, se retoma la preparación de backup real
