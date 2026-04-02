# Fase 6 MVP: inference gateway

## objetivo

Definir un gateway interno para que los agentes consuman inferencia sin ver credenciales reales.

## contrato técnico mínimo

- endpoint interno único, por ejemplo `inference.local` o alias equivalente
- interfaz HTTP interna estable
- endpoint de salud simple
- forwarding solo a proveedores aprobados

## allowlist mínima

- upstreams de inferencia aprobados
- salida HTTPS únicamente a esos upstreams
- denegación por defecto del resto

## logging esperado

- timestamp
- agente o cliente origen
- modelo o alias solicitado
- código de respuesta
- latencia
- sin payloads completos
- sin tokens ni secretos

## consumo por agentes

- los agentes llaman al gateway interno
- los tokens reales viven solo en el servicio gateway
- los agentes trabajan con alias o variables no sensibles

## que faltaria para desplegarlo

- ruta/hostname interno definitivo
- servicio o contenedor del gateway
- inyección segura de secretos
- política final de logging
- prueba de consumo desde la futura zona de agentes

## limite actual

- arquitectura definida
- despliegue real pendiente de acceso operativo y gestión de secretos
