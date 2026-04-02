# Fase 5 MVP: zona de agentes

## objetivo

Definir una zona separada para futuros agentes sin tocar todavía el host general ni abrir egress amplio por defecto.

## diseño mínimo

- runtime previsto en una zona propia bajo `/opt`, separada del resto de servicios del VPS
- ejecución encapsulada mediante wrappers readonly/operativos explícitos
- sin acceso directo a secretos del host
- sin acceso implícito a Docker, NPM ni `devops`

## aislamiento previsto

- red propia o segmento lógico dedicado para agentes
- acceso saliente mínimo y explícito
- acceso entrante no requerido salvo API internas justificadas
- volúmenes o bind mounts solo si están declarados y auditados

## egress mínimo inicial

- DNS
- HTTPS saliente solo a destinos aprobados
- acceso interno solo a endpoints definidos del propio plan, no al host completo

## wrappers previstos

- wrappers readonly para inventario, estado y validación
- wrappers operativos mínimos y auditables para acciones futuras justificadas
- sin shell libre ni sudo general para agentes

## checklist de implantación

- definir red y límites
- crear wrappers mínimos
- declarar allowlist de egress
- probar un agente piloto sin acceso a secretos
- validar que no afecta al host general

## checklist de rollback

- detener runtime de agentes
- retirar red o segmento dedicado
- retirar wrappers del piloto
- confirmar que el host principal sigue igual

## limites y supuestos

- este documento deja la arquitectura implantable
- no implica despliegue realizado
- depende de una ventana posterior con acceso operativo real al host
