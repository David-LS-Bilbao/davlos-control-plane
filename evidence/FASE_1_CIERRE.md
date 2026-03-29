# Cierre Fase 1

## Objetivo
Inventario real del VPS, detección de rutas fuente de verdad y creación inicial del control-plane sin mover servicios críticos.

## Comprobaciones realizadas
- Host validado
- Contenedores activos inventariados
- Layout real de /opt inventariado
- Verity prod validado contra Docker labels:
  - WORKDIR=/opt/verity-stack/verity-news
  - CONFIG=/opt/verity-stack/verity-news/compose.yml
- n8n confirmado como dependiente operativamente de /root:
  - /root/docker-compose.yaml
  - /root/n8n.env
  - /root/local-files
  - volumen Docker root_n8n_data
- control-plane creado y versionado con Git

## Riesgos detectados
- n8n sigue fuera del layout objetivo
- layout por zonas aún no formalizado
- no se deben mezclar todavía reordenación estructural y migración de n8n

## Rollback
No aplica a servicios críticos.
En esta fase solo se creó /opt/control-plane y documentación asociada.

## Estado de cierre
Fase 1 cerrada.
La siguiente fase debe centrarse en la definición formal del layout final por zonas.
