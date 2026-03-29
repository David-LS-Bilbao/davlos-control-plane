# Inventario inicial del VPS

## Host y sistema
- Usuario operativo: devops
- Hostname: ubuntu
- Sistema operativo: Ubuntu 24.04.4 LTS
- Kernel: Linux 6.8.0-101-generic
- Arquitectura: x86-64
- Virtualización: KVM

## Layout real actual en /opt
- /opt/containerd
- /opt/verity-postgres
- /opt/verity-stack
- /opt/verity-stack/npm
- /opt/verity-stack/staging
- /opt/verity-stack/verity-news

## Servicios activos detectados
- verity_npm
- root-n8n-1
- verity_news_frontend
- verity_news_backend
- verity-postgres-postgres-1
- veritynews-frontend-staging
- veritynews-backend-staging
- veritynews-postgres-staging
- veritynews-redis-staging

## Fuentes de verdad operativa probables
- Nginx Proxy Manager: /opt/verity-stack/npm/docker-compose.yml
- Verity News producción: /opt/verity-stack/verity-news
- Verity News staging: /opt/verity-stack/staging/verity-news-staging/docker-compose.yml
- PostgreSQL producción: /opt/verity-postgres/docker-compose.yml
- n8n: /root/docker-compose.yaml + /root/n8n.env + /root/local-files

## Evidencia específica de n8n
- Contenedor activo: root-n8n-1
- Puerto publicado: 127.0.0.1:5678->5678/tcp
- Volumen persistente: /var/lib/docker/volumes/root_n8n_data/_data -> /home/node/.n8n
- Bind mount adicional: /root/local-files -> /files
- Red usada: verity_network

## Deuda técnica detectada
- n8n sigue dependiendo operativamente de /root
- el layout objetivo por zonas aún no está formalizado en /opt
- existen rutas heredadas fuera del futuro esquema /opt/apps, /opt/automation, /opt/infra, /opt/control-plane y /opt/backups

## Riesgos antes de siguientes fases
- mover n8n sin backup y rollback
- tocar /root/local-files sin inventariar su uso
- mezclar reordenación del layout con migración operativa en un solo paso

## Conclusión de Fase 1
La realidad operativa del VPS ya está identificada. La principal deuda técnica prioritaria es la dependencia de n8n respecto a /root. No se han realizado cambios en producción durante esta fase.

