# Runbook de ejecución de prechecks para n8n

## Objetivo

Definir el pack mínimo ejecutable de prechecks para `n8n` antes de cualquier preparación de migración fuera de `/root`.

Este runbook no mueve servicios.
Este runbook no modifica `compose`, `env` ni mounts activos.
Este runbook no expone secretos.

## Alcance

Este runbook cubre únicamente:

- verificación base del host y del repo
- verificación de acceso operativo a Docker y a `/root`
- comprobaciones inocuas de accesibilidad de `n8n` y NPM
- inspección de solo lectura del runtime de `n8n` si ya existe acceso suficiente
- inventario técnico mínimo para decidir la siguiente fase

No cubre:

- ejecución de backup
- cambios de layout
- cambios de proxy
- migración
- rollback ejecutado

## Prerrequisitos

- ejecutar desde `/opt/control-plane`
- usar una sesión controlada
- no exponer secretos en terminal ni en logs
- si `devops` no tiene acceso a Docker o `/root`, ejecutar la parte avanzada solo con root o con acceso equivalente de solo lectura

## Estructura de scripts

Ruta base:

- `scripts/prechecks/n8n/`

Scripts incluidos:

1. `00_host_repo_baseline.sh`
2. `10_access_prereqs.sh`
3. `20_n8n_runtime_probe.sh`
4. `30_n8n_docker_readonly.sh`
5. `40_n8n_inventory_minimum.sh`

## Orden exacto de ejecución recomendado

### 1. Línea base del host y repo

```bash
./scripts/prechecks/n8n/00_host_repo_baseline.sh
```

Resultado esperado:

- confirma usuario, host, repo, estado git, estructura base y puertos en escucha

### 2. Verificación de acceso operativo

```bash
./scripts/prechecks/n8n/10_access_prereqs.sh
```

Resultado esperado:

- confirma si la sesión actual tiene acceso suficiente a Docker y a `/root`

Criterio:

- si este paso falla, no continuar con inspección avanzada
- registrar el bloqueo como hallazgo operativo, no como error de documentación

### 3. Sonda inocua de runtime

```bash
./scripts/prechecks/n8n/20_n8n_runtime_probe.sh
```

Resultado esperado:

- confirma que `n8n` responde en loopback
- confirma que NPM responde localmente
- confirma que el puerto `5678` sigue en escucha

### 4. Inspección Docker de solo lectura

Ejecutar solo si el paso 2 confirma acceso suficiente.

```bash
./scripts/prechecks/n8n/30_n8n_docker_readonly.sh
```

Resultado esperado:

- imagen, estado y restart policy
- mounts del contenedor
- red o redes activas
- volumen persistente esperado
- claves de entorno, nunca valores

### 5. Inventario técnico mínimo

Ejecutar solo si el paso 4 fue viable.

```bash
./scripts/prechecks/n8n/40_n8n_inventory_minimum.sh
```

Resultado esperado:

- indicio de SQLite o ausencia de evidencia suficiente
- confirmación mínima de mounts y rutas
- indicio de uso de `/root/local-files`
- base técnica para cerrar el inventario mínimo útil

## Evidencia a registrar

Guardar la salida en una ruta de evidencia fechada, por ejemplo:

- `evidence/prechecks/n8n/2026-03-30/`

Forma recomendada:

```bash
mkdir -p evidence/prechecks/n8n/2026-03-30
./scripts/prechecks/n8n/00_host_repo_baseline.sh | tee evidence/prechecks/n8n/2026-03-30/00_host_repo_baseline.txt
./scripts/prechecks/n8n/10_access_prereqs.sh | tee evidence/prechecks/n8n/2026-03-30/10_access_prereqs.txt
./scripts/prechecks/n8n/20_n8n_runtime_probe.sh | tee evidence/prechecks/n8n/2026-03-30/20_n8n_runtime_probe.txt
./scripts/prechecks/n8n/30_n8n_docker_readonly.sh | tee evidence/prechecks/n8n/2026-03-30/30_n8n_docker_readonly.txt
./scripts/prechecks/n8n/40_n8n_inventory_minimum.sh | tee evidence/prechecks/n8n/2026-03-30/40_n8n_inventory_minimum.txt
```

Nota:

- los pasos 4 y 5 solo deben ejecutarse si el acceso operativo lo permite

## Criterio de salida

Se puede pasar a preparar backup mínimo real cuando, como mínimo, queden confirmados:

- compose activo real
- env file activo real, al menos por ruta y claves
- mounts activos reales
- volumen persistente real
- red real del contenedor
- tipo de base de datos real o ausencia documentada de evidencia suficiente
- inventario mínimo útil de workflows/webhooks/dependencia de archivos

No debe pasarse a implantación mientras alguno de esos puntos siga abierto.

## Fallo y parada

Debe pararse la secuencia si ocurre cualquiera de estas condiciones:

- no hay acceso suficiente a Docker
- no hay acceso suficiente a `/root`
- `n8n` no responde en `127.0.0.1:5678`
- la información real contradice la documentación histórica sin explicación clara
- la inspección de solo lectura empieza a requerir acceso a secretos o cambios activos

## Siguiente fase recomendada

Si los prechecks salen bien:

1. cerrar backup mínimo real
2. cerrar rollback mínimo real
3. preparar directorios objetivo fuera de `/root` sin mover producción
4. aprobar una ventana posterior de implantación
