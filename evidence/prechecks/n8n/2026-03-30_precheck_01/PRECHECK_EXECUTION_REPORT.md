# Ejecución de prechecks n8n

## 1. Resumen

Resultado global de la ejecución: `PARTIAL`.

La secuencia de prechecks se ejecutó correctamente hasta el punto en que era posible mantener un modo estrictamente no destructivo desde el usuario `devops`.

Hallazgo principal:

- `n8n` está operativo y responde localmente en `127.0.0.1:5678`
- el acceso a Docker y a rutas bajo `/root` sigue bloqueado para `devops`
- por ese motivo la ejecución se detuvo correctamente en `30_n8n_docker_readonly.sh`
- `40_n8n_inventory_minimum.sh` no se ejecutó

## 2. Scripts ejecutados

Ejecutados con evidencia capturada:

- `00_host_repo_baseline.sh`
- `10_access_prereqs.sh`
- `20_n8n_runtime_probe.sh`
- `30_n8n_docker_readonly.sh`

No ejecutado por bloqueo previo:

- `40_n8n_inventory_minimum.sh`

## 3. Hallazgos confirmados

- el pack de prechecks y los runbooks requeridos existen en `/opt/control-plane`
- el control-plane sigue ubicado en `/opt/control-plane`
- el usuario operativo actual es `devops`
- el host es Ubuntu 24.04.4 LTS sobre KVM
- `n8n` escucha en `127.0.0.1:5678`
- `n8n` responde con `HTTP/1.1 200 OK` por loopback
- NPM escucha en `127.0.0.1:81`
- NPM responde con `HTTP/1.1 200 OK` por loopback
- `devops` no tiene acceso directo al socket Docker
- `/root/docker-compose.yaml`, `/root/n8n.env` y `/root/local-files` están bloqueados para `devops`

## 4. Hallazgos probables

- `n8n` sigue dependiendo operativamente de `/root`, en línea con la evidencia histórica del control-plane
- el acceso operativo a `n8n` sigue estando mediado por proxy/reverse proxy y no por exposición pública directa del puerto `5678`
- `root-n8n-1`, `root_n8n_data` y `verity_network` siguen siendo referencias plausibles de runtime, pero no han podido reconfirmarse en esta ejecución

## 5. Bloqueos

Bloqueo principal:

- falta acceso de solo lectura a Docker y a `/root`

Accesos concretos ausentes:

- `docker ps` no es utilizable desde `devops`
- `sudo -n` no está disponible para ejecutar Docker sin interacción
- no es posible inspeccionar:
  - contenedor real de `n8n`
  - mounts reales
  - volumen real
  - red real
  - tipo de base de datos real
  - inventario técnico mínimo dentro de la instancia

## 6. Riesgos actuales

- riesgo de falsa confianza si se asume que la documentación histórica sustituye a la verificación runtime real
- riesgo de preparar backup o migración sin haber validado contenedor, mounts y volumen efectivos
- riesgo de subestimar la dependencia real de `/root/local-files`
- riesgo de no detectar a tiempo diferencias entre la documentación existente y la instancia activa

## 7. Si ya estamos listos o no para backup real + ventana de migración

Estado: `no`.

Motivo:

- todavía no existe verificación runtime suficiente para preparar con garantías una ventana de backup real
- antes de eso hay que cerrar acceso operativo de solo lectura a Docker y a `/root`
- sin esa capa, el backup podría quedar incompleto o mal orientado

## 8. Siguiente paso exacto recomendado

Abrir una sesión controlada con acceso Docker/root de solo lectura y repetir desde:

1. `30_n8n_docker_readonly.sh`
2. `40_n8n_inventory_minimum.sh`

Si ambos pasos cierran correctamente:

3. consolidar evidencia en el control-plane
4. validar compose/env/mounts/volumen reales
5. solo entonces preparar la ventana de backup real
