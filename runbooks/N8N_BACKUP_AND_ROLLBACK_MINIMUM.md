# Runbook mínimo de backup y rollback para n8n

## Objetivo

Definir el mínimo operativo de backup y rollback que debe quedar preparado antes de cualquier migración futura de `n8n` fuera de `/root`.

Este runbook no ejecuta cambios en esta tarea.
Este runbook no autoriza una migración.
Este runbook no debe aplicarse sin ventana aprobada y acceso operativo suficiente.

## Alcance

Este runbook cubre:

- qué artefactos deben copiarse
- qué evidencia mínima debe capturarse
- qué orden seguir para un backup seguro
- qué rollback mínimo debe poder ejecutarse si la migración falla

No cubre:

- restauración completa probada
- tuning de tiempos
- migración real

## Artefactos mínimos a respaldar

Antes de mover nada, debe existir respaldo verificable de:

- `/root/docker-compose.yaml`
- `/root/n8n.env`
- `/root/local-files`
- contenido persistente del volumen `root_n8n_data`

Adicionalmente conviene capturar en evidencia:

- estado del contenedor `n8n`
- mounts activos
- red o redes activas
- claves de entorno, nunca valores

## Ubicación objetivo recomendada

No guardar backups dentro del repositorio Git.

Ubicaciones recomendadas:

- `/opt/backups/n8n/DATE/`
- subdirectorios:
  - `compose/`
  - `env/`
  - `local-files/`
  - `volume/`
  - `evidence/`

## Secuencia mínima de backup

Ejecutar solo con acceso autorizado y de solo lectura sobre origen.

### 1. Crear carpeta de backup

```bash
DATE="$(date +%F-%H%M%S)"
sudo mkdir -p "/opt/backups/n8n/${DATE}"/{compose,env,local-files,volume,evidence}
```

### 2. Copiar compose activo

```bash
sudo cp --preserve=all /root/docker-compose.yaml "/opt/backups/n8n/${DATE}/compose/"
```

### 3. Copiar env activo sin imprimir contenido

```bash
sudo cp --preserve=all /root/n8n.env "/opt/backups/n8n/${DATE}/env/"
sudo sh -c "grep -E '^[A-Z0-9_]+=' /root/n8n.env | cut -d= -f1 | sort -u > /opt/backups/n8n/${DATE}/evidence/n8n_env_keys.txt"
```

### 4. Copiar bind mount de archivos

```bash
sudo rsync -aHAX --numeric-ids /root/local-files/ "/opt/backups/n8n/${DATE}/local-files/"
```

### 5. Copiar persistencia del volumen

```bash
sudo tar -C /var/lib/docker/volumes/root_n8n_data/_data -cpf "/opt/backups/n8n/${DATE}/volume/root_n8n_data.tar" .
```

### 6. Capturar evidencia técnica mínima

```bash
sudo docker inspect root-n8n-1 > "/opt/backups/n8n/${DATE}/evidence/docker_inspect_root-n8n-1.json"
sudo docker volume inspect root_n8n_data > "/opt/backups/n8n/${DATE}/evidence/docker_volume_root_n8n_data.json"
sudo docker network inspect verity_network > "/opt/backups/n8n/${DATE}/evidence/docker_network_verity_network.json"
```

### 7. Verificación mínima del backup

```bash
sudo du -sh "/opt/backups/n8n/${DATE}"/compose "/opt/backups/n8n/${DATE}"/env "/opt/backups/n8n/${DATE}"/local-files "/opt/backups/n8n/${DATE}"/volume
sudo sha256sum "/opt/backups/n8n/${DATE}/volume/root_n8n_data.tar" | sudo tee "/opt/backups/n8n/${DATE}/evidence/sha256sums.txt"
```

## Criterio mínimo de backup aceptable

El backup no debe considerarse suficiente si falta cualquiera de estos puntos:

- compose copiado
- env copiado
- `local-files` copiado
- volumen copiado
- evidencia técnica mínima capturada
- verificación básica de tamaño o checksum

## Rollback mínimo que debe poder ejecutarse

El rollback mínimo debe permitir volver al último estado conocido usando:

- compose previo
- env previo
- `local-files` previo
- persistencia previa
- misma topología de acceso esperada

## Secuencia conceptual mínima de rollback

Ejecutar solo en una ventana aprobada si la migración ha fallado.

### 1. Detener el stack nuevo o fallido

Acción prevista:

- detener el stack fallido antes de restaurar artefactos previos

### 2. Restaurar compose y env previos

Comandos de referencia:

```bash
sudo cp --preserve=all "/opt/backups/n8n/${DATE}/compose/docker-compose.yaml" /root/docker-compose.yaml
sudo cp --preserve=all "/opt/backups/n8n/${DATE}/env/n8n.env" /root/n8n.env
```

### 3. Restaurar `local-files`

Comando de referencia:

```bash
sudo rsync -aHAX --delete --numeric-ids "/opt/backups/n8n/${DATE}/local-files/" /root/local-files/
```

### 4. Restaurar persistencia

Comando de referencia:

```bash
sudo tar -C /var/lib/docker/volumes/root_n8n_data/_data -xpf "/opt/backups/n8n/${DATE}/volume/root_n8n_data.tar"
```

### 5. Revalidar servicio

Comprobaciones mínimas:

- `n8n` vuelve a responder localmente
- los mounts críticos vuelven a estar presentes
- el acceso esperado por proxy sigue operativo
- los workflows esperados siguen presentes

## Riesgos que este runbook intenta cubrir

- pérdida de persistencia
- pérdida de entorno
- pérdida de archivos montados
- falsa equivalencia entre layout nuevo y estado operativo real
- rollback incompleto por no haber copiado todos los artefactos

## Condición de uso

Este runbook debe usarse solo después de:

1. ejecutar prechecks
2. confirmar acceso operativo suficiente
3. definir la ventana de trabajo
4. aprobar el cambio
