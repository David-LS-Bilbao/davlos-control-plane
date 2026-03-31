# Allowlist / egress MVP de la zona de agentes

## objetivo

Definir la salida mínima prevista para `agents_net` sin bloquear el MVP de mañana.

## politica prevista

- denegación por defecto cuando se aplique de verdad
- permitir solo lo necesario para OpenClaw y sus proveedores aprobados

## salida mínima candidata

- DNS hacia resolvers definidos del host
- HTTPS saliente a:
  - proveedor LLM aprobado
  - repositorios estrictamente necesarios durante instalación/actualización
  - endpoints internos aprobados como futuro `inference.local`

## no permitido por defecto

- acceso libre al host completo
- salida arbitraria a Internet
- acceso a `verity_network` salvo caso justificado y documentado

## estado actual

- diseño definido
- allowlist real no aplicada todavía en runtime
- pendiente de ejecutar en una siguiente ventana operativa
