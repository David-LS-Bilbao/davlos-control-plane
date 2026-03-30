# INTERVENCIÓN 2 — GUION OPERATIVO FINAL (SAFE)

## 0. REGLAS

- Ejecutar desde una shell con permisos para sudo.
- No tocar NPM.
- No renombrar root_n8n_data.
- No borrar nada bajo /root.
- Usar curl sin sudo.
- Usar docker solo con sudo.
- No imprimir el contenido de n8n.env.
- No mostrar en pantalla el docker compose config completo del stack nuevo.
- Si un comando crítico no devuelve lo esperado, parar en ese punto.
- Si el rollback no devuelve 127.0.0.1:5678 a HTTP/1.1 200 OK, no insistir.

## 1. PRE-CAPTURE

- comandos exactos

```bash
sudo date -u
sudo hostnamectl --static

sudo docker compose -f /root/docker-compose.yaml config --services
sudo docker compose -f /root/docker-compose.yaml ps

sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'root-n8n-1|verity_npm'

sudo docker inspect root-n8n-1 --format 'status={{.State.Status}} restart={{.HostConfig.RestartPolicy.Name}}'
sudo docker inspect root-n8n-1 --format 'ports={{json .NetworkSettings.Ports}}'
sudo docker inspect root-n8n-1 --format 'networks={{range $k, $v := .NetworkSettings.Networks}}{{printf "%s " $k}}{{end}}'
sudo docker inspect root-n8n-1 --format 'mounts={{range .Mounts}}{{printf "%s:%s:%s\n" .Type .Source .Destination}}{{end}}'

sudo docker volume inspect root_n8n_data --format 'name={{.Name}} mountpoint={{.Mountpoint}}'
sudo docker network inspect verity_network --format 'name={{.Name}} driver={{.Driver}}'

curl -I http://127.0.0.1:5678
curl -I http://127.0.0.1:81

TMP_RENDER="$(mktemp /tmp/n8n-compose.XXXXXX.yaml)"
chmod 600 "$TMP_RENDER"

sudo docker compose \
  --env-file /opt/automation/n8n/env/n8n.env \
  -f /opt/automation/n8n/compose/docker-compose.yaml \
  config > "$TMP_RENDER"

grep -nF 'host_ip: 127.0.0.1' "$TMP_RENDER"
grep -nF 'published: "5678"' "$TMP_RENDER"
grep -nF 'target: 5678' "$TMP_RENDER"
grep -nF 'name: verity_network' "$TMP_RENDER"
grep -nF 'source: root_n8n_data' "$TMP_RENDER"
grep -nF 'source: /opt/automation/n8n/local-files' "$TMP_RENDER"
grep -nF 'target: /files' "$TMP_RENDER"
grep -nE 'restart:\s*unless-stopped' "$TMP_RENDER"

rm -f "$TMP_RENDER"
unset TMP_RENDER
```
