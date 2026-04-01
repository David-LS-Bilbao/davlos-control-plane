# Plan de ejecución — OpenClaw en VPS DAVLOS
**Fecha:** 2026-03-31  
**Autoría del plan:** ChatGPT  
**Objetivo:** convertir el MVP actual de OpenClaw en una pieza útil, segmentada y controlada dentro del VPS DAVLOS, con evolución segura hacia acciones restringidas, observabilidad, chat/Telegram y operación asistida mediante Codex CLI.

---

## 1. Resumen ejecutivo

El objetivo no es dar a OpenClaw acceso general al VPS, sino integrarlo como **agente aislado** dentro de una **zona de agentes** separada, con estas premisas:

- **Zona Apps**: despliegue de aplicaciones como Verity News.
- **Zona Automation**: n8n y sus automatizaciones, accesible por su gateway.
- **Zona Agents**: OpenClaw, bajo control, sin acceso implícito al host ni a otras zonas.
- **Infra compartida**: NPM, PostgreSQL, WireGuard, inference-gateway, Ollama.

La línea correcta de evolución es:

**Canal de entrada (chat / Telegram / consola)  
→ controlador restringido / broker de acciones  
→ OpenClaw como razonador  
→ ejecución sólo de acciones permitidas  
→ auditoría completa**

Este plan está pensado para ejecutarse con **Codex CLI** en el VPS, por fases pequeñas, verificables y reversibles.

---

## 2. Estado de partida asumido

Se toma como base operativa lo ya descrito y validado:

### 2.1 Base estable del VPS
- Verity News, n8n, NPM, WireGuard y PostgreSQL deben seguir fuera de alcance de cambios no planificados.
- No se debe romper el runtime existente.
- No se introducen secretos en el repositorio.

### 2.2 OpenClaw
Estado funcional MVP asumido:
- contenedor `openclaw-gateway` en running
- bind local `127.0.0.1:18789 -> 18789`
- red `agents_net`
- health suficiente para MVP
- inferencia contra gateway intermedio

### 2.3 Inference gateway
- servicio host-side por `systemd`
- escucha en `127.0.0.1:11440`
- accesible desde `agents_net` vía `172.22.0.1:11440`
- northbound mínimo:
  - `/healthz`
  - `/v1/models`
  - `/v1/chat/completions`

### 2.4 Topología actual válida
`OpenClaw -> http://172.22.0.1:11440/v1 -> inference-gateway -> Ollama host (127.0.0.1:11434)`

---

## 3. Objetivo técnico final

Llegar a una arquitectura donde:

1. **OpenClaw permanezca aislado** de apps, automatización e infra.
2. **No exista acceso libre a shell, Docker, systemd ni rutas sensibles** desde OpenClaw.
3. **Las acciones operativas se expongan como capacidades predefinidas**.
4. **La DAVLOS VPN Console pueda abrir/cerrar capacidades** desde un menú.
5. **OpenClaw pueda recibir peticiones por chat web, Telegram o ambos**, pero siempre pasando por el mismo backend restringido.
6. **Codex CLI se use para construir y evolucionar el sistema**, no como un atajo para dar ejecución arbitraria al agente.
7. **Toda acción quede auditada**.

---

## 4. Principios de diseño obligatorios

### 4.1 Mínimo privilegio
OpenClaw sólo podrá hacer aquello que se le permita de forma explícita.

### 4.2 Nada de ejecución arbitraria
No se debe permitir:
- shell arbitraria
- acceso al Docker socket
- `systemctl` general
- lectura de secretos globales
- acceso directo a `verity_network`
- acceso libre a `/opt`, `/root` o producción

### 4.3 Contratos entre zonas
Ninguna zona debe tocar otra directamente salvo a través de interfaces mínimas y auditables.

### 4.4 Control temporal
Las capacidades sensibles deben poder activarse con TTL y revocación automática.

### 4.5 Evidencia y trazabilidad
Cada cambio y cada acción operativa deben dejar rastro:
- quién
- qué
- cuándo
- por qué
- resultado
- expiración si aplica

---

## 5. Arquitectura objetivo

## 5.1 Zonas

### Zona Apps
- Verity News y futuros despliegues de apps
- sin acceso directo desde OpenClaw

### Zona Automation
- n8n
- accesible sólo por webhooks/endpoints permitidos
- no exponer editor ni runtime interno a OpenClaw

### Zona Agents
- OpenClaw
- future agents
- salida limitada sólo a destinos aprobados

### Infra compartida
- inference-gateway
- Ollama
- NPM
- PostgreSQL
- WireGuard

---

## 5.2 Plano lógico de control

**Canales**
- chat interno web
- Telegram privado
- DAVLOS VPN Console

**Broker / restricted operator**
- servicio local que recibe solicitudes
- consulta políticas activas
- ejecuta wrappers concretos
- deja logs

**OpenClaw**
- interpreta intención
- propone o solicita acciones
- nunca ejecuta directamente operaciones host-side sensibles

**Policy store**
- permisos activos y expiraciones

**Audit log**
- trazabilidad de cada acción y cada cambio de permiso

---

## 6. Capacidades predefinidas (modelo A/B/C/D/...)

La idea es que el menú no “dé acceso al host”, sino que active/desactive **capacidades cerradas**.

### Estados recomendados
- `disabled`
- `readonly`
- `restricted`
- `ttl_enabled`
- `one_shot`

### Capacidades iniciales recomendadas

#### Acción A — Health general
Permitido:
- health de OpenClaw
- health de inference-gateway
- health de Verity
- health de n8n

Riesgo: bajo  
Modo recomendado: `readonly`

#### Acción B — Logs permitidos
Permitido:
- lectura de logs allowlisted
- últimas N líneas
- rutas cerradas

Riesgo: bajo/medio  
Modo recomendado: `readonly`

#### Acción C — Disparo de webhook concreto de n8n
Permitido:
- un endpoint o varios explícitos
- payload validado
- rate limit
- timeout

Riesgo: medio  
Modo recomendado: `restricted` + TTL

#### Acción D — Reinicio de OpenClaw
Permitido:
- reiniciar sólo `openclaw-gateway`
- nunca otros servicios

Riesgo: medio  
Modo recomendado: `restricted` + TTL

#### Acción E — Escritura en drop-zone controlada
Permitido:
- escribir sólo en rutas definidas
- sin tocar producción

Riesgo: medio  
Modo recomendado: `restricted`

#### Acción F — Operación sobre staging
Permitido:
- sólo endpoints/rutas del entorno staging
- nunca prod

Riesgo: medio  
Modo recomendado: `restricted`

### Acciones que NO deben abrirse en esta fase
- shell arbitraria
- Docker genérico
- systemd genérico
- firewall/UFW
- lectura de secretos
- acceso a bases de datos
- manipulación de producción

---

## 7. Fases de ejecución

## Fase 0 — Congelación y alineación documental
### Objetivo
Alinear el repositorio con el estado real antes de seguir construyendo.

### Entregables
- README actualizado con OpenClaw + inference gateway + límites
- `docs/AGENTS.md` actualizado
- clasificación de documentos históricos vs vigentes
- checklist de merge/limpieza de rama OpenClaw
- eliminación de salidas que puedan exponer secretos en scripts

### Criterio de salida
El repo deja de tener mensajes contradictorios sobre si OpenClaw está staged o desplegado.

---

## Fase 1 — Consolidación de la zona de agentes
### Objetivo
Dejar la zona de agentes claramente delimitada como trust boundary.

### Entregables
- layout definitivo documentado para OpenClaw
- contratos de mounts permitidos
- definición de secretos host-side
- decisión sobre imagen pin por digest
- healthcheck más semántico si procede

### Criterio de salida
OpenClaw sigue operativo, aislado y con contratos claros.

---

## Fase 2 — Restricted Operator / Broker local
### Objetivo
Crear la pieza intermedia que ejecute únicamente acciones preaprobadas.

### Responsabilidades del broker
- exponer API interna local
- mapear `action_id` -> wrapper permitido
- validar parámetros
- rechazar acciones no permitidas
- registrar auditoría

### Entregables
- diseño del broker
- estructura de acciones
- wrappers iniciales A/B/C/D/E
- política base de permisos
- formato de auditoría

### Criterio de salida
OpenClaw puede pedir acciones, pero no ejecutar nada fuera del broker.

---

## Fase 3 — Policy store y TTL de permisos
### Objetivo
Permitir abrir/cerrar capacidades desde política viva.

### Entregables
- `permissions.json` o `permissions.d/*.yaml`
- soporte para:
  - enable/disable
  - TTL
  - one-shot
  - readonly/restricted
- comando de inspección de política activa
- expiración automática

### Criterio de salida
Las capacidades sensibles pueden darse temporalmente y revocarse sin intervención manual posterior.

---

## Fase 4 — Integración con DAVLOS VPN Console
### Objetivo
Hacer que la consola deje de ser sólo observabilidad y pase a ser panel de control de capacidades.

### Opciones mínimas del menú
- ver estado de capacidades
- permitir Acción A/B/C/D
- permitir con TTL
- revocar
- cerrar todas las temporales
- ver auditoría
- volver a modo readonly global

### Entregables
- nuevo menú `capabilities`
- submenú OpenClaw
- integración con policy store
- mensajes claros de estado

### Criterio de salida
El operador puede abrir/cerrar capacidades desde menú sin tocar archivos manualmente.

---

## Fase 5 — Canales de entrada: chat y/o Telegram
### Objetivo
Permitir operar con OpenClaw por chat manteniendo las mismas restricciones.

### Estrategia recomendada
Primero:
- chat interno/web o canal local controlado

Después:
- Telegram bot privado

### Reglas
- ambos canales usan el mismo broker
- autenticación obligatoria
- autorización por usuario/rol
- auditoría completa
- sin exponer control directo del host

### Entregables
- interfaz de chat elegida
- especificación de comandos/intenciones
- integración Telegram opcional
- política de identidad/autorización

### Criterio de salida
Se puede hablar con el agente sin darle poder libre sobre el VPS.

---

## Fase 6 — Egress real y endurecimiento de red
### Objetivo
Pasar de la allowlist documental a enforcement real.

### Entregables
- allowlist aplicada para `agents_net`
- destinos mínimos aprobados
- denegación por defecto cuando toque
- validación de que OpenClaw no ve `verity_network`
- limpieza fina de reglas residuales

### Criterio de salida
OpenClaw sólo puede salir a destinos aprobados.

---

## Fase 7 — Observabilidad y auditoría
### Objetivo
Hacer visible y trazable todo lo que haga el plano de agentes.

### Logs mínimos
- apertura/cierre de capacidades
- expiraciones automáticas
- solicitudes de OpenClaw
- acciones aceptadas
- acciones rechazadas
- errores de wrappers
- trazas de canal (chat / Telegram / consola)

### Entregables
- formato de log
- ubicación de logs
- vistas readonly en consola
- comandos de revisión rápida

### Criterio de salida
Cada acción puede reconstruirse a posteriori.

---

## Fase 8 — Validación funcional y cierre de MVP ampliado
### Objetivo
Cerrar un MVP ampliado útil y seguro.

### Casos de prueba mínimos
- health general
- lectura de logs permitidos
- trigger de webhook concreto
- reinicio sólo de OpenClaw
- expiración TTL
- revocación manual
- rechazo de acción no permitida
- rechazo de parámetro fuera de allowlist
- operación por consola
- operación por chat
- operación por Telegram si se implementa

### Criterio de salida
Sistema útil, reversible y auditable.

---

## 8. Orden recomendado de ejecución real

1. Fase 0 — alinear repo y limpiar contradicciones
2. Fase 1 — consolidar zona de agentes
3. Fase 2 — construir broker restringido
4. Fase 3 — política con TTL
5. Fase 4 — integrar menú en DAVLOS VPN Console
6. Fase 7 — observabilidad/auditoría básica
7. Fase 5 — canal de chat interno
8. Fase 5b — Telegram privado
9. Fase 6 — egress real más estricto
10. Fase 8 — validación final

---

## 9. Qué debe hacer Codex CLI en este proyecto

Codex debe usarse como **herramienta de ingeniería asistida**, no como root automático del VPS.

### Sí usar Codex para
- generar/refactorizar scripts
- crear el broker/restricted operator
- crear el policy store
- ampliar la consola
- redactar runbooks y docs
- crear tests y validaciones
- revisar scripts por seguridad

### No usar Codex para
- dar shell arbitraria al agente
- automatizar cambios peligrosos sin guardarraíles
- ejecutar acciones fuera del contrato definido
- gestionar secretos en claro
- tocar servicios de producción sin fase y validación

---

## 10. Estilo de prompts para Codex CLI

### Reglas
- pedir siempre cambios pequeños
- exigir diffs mínimos
- pedir rollback mental
- pedir criterio de aceptación
- pedir no tocar runtime sensible salvo lo solicitado
- pedir no exponer secretos ni valores de `.env`

---

## 11. Prompts maestros recomendados para la ejecución

## Prompt maestro Fase 0
Actúa como Tech Lead de plataforma y seguridad para el proyecto DAVLOS Control-Plane.

Objetivo:
alinear la rama de OpenClaw con el estado real del proyecto y dejar la documentación coherente antes de seguir desarrollando.

Tareas:
1. revisa README, docs/AGENTS.md y documentos base relacionados con OpenClaw e inference-gateway
2. detecta contradicciones entre documentación y evidencia
3. propone un parche mínimo para dejar una única verdad operativa vigente
4. revisa scripts de despliegue para evitar impresión accidental de secretos
5. no introduzcas secretos ni valores reales
6. no cambies runtime del VPS; solo repo y documentación
7. entrega:
   - resumen de hallazgos
   - diff propuesto
   - riesgos
   - checklist de validación

Restricciones:
- no tocar n8n
- no tocar Verity
- no tocar NPM/WireGuard/PostgreSQL
- no asumir que diseño = estado real
- no imprimir contenido de `.env`

---

## Prompt maestro Fase 1
Actúa como Platform Engineer senior.

Objetivo:
consolidar la zona de agentes de OpenClaw como trust boundary operativa dentro del VPS DAVLOS.

Tareas:
1. revisa layout, Compose, mounts, secretos host-side y healthcheck actual
2. propone endurecimientos MVP realistas
3. prioriza:
   - pin por digest
   - healthcheck semántico si es viable
   - contratos de rutas/mounts
   - documentación final de límites
4. no toques producción fuera de OpenClaw
5. entrega:
   - plan técnico corto
   - diff mínimo
   - validaciones exactas post-cambio
   - rollback

Restricciones:
- no dar acceso a Docker socket
- no añadir acceso a `verity_network`
- no abrir Internet libre
- no tocar n8n ni Verity

---

## Prompt maestro Fase 2
Actúa como Software Architect + Backend Engineer.

Objetivo:
diseñar e implementar un restricted operator local para OpenClaw.

Tareas:
1. crea una propuesta de arquitectura para un broker local de acciones
2. define formato de política de permisos
3. implementa una primera versión con acciones:
   - A health general
   - B logs permitidos
   - C trigger de webhook concreto
   - D restart solo OpenClaw
   - E escritura en drop-zone
4. cada acción debe ser cerrada, validable y auditable
5. no permitir comandos arbitrarios
6. entrega:
   - arquitectura
   - árbol de ficheros
   - código
   - pruebas básicas
   - ejemplos de política
   - riesgos y siguientes pasos

Restricciones:
- sin shell arbitraria
- sin Docker general
- sin systemd general
- sin lectura de secretos
- sin acceso a producción fuera de wrappers explícitos

---

## Prompt maestro Fase 3
Actúa como Backend Engineer.

Objetivo:
añadir política viva con TTL para capacidades de OpenClaw.

Tareas:
1. diseña el formato `permissions.json` o equivalente
2. soporta:
   - enabled/disabled
   - readonly/restricted
   - expires_at
   - one_shot
3. implementa expiración automática segura
4. añade comandos o utilidades para inspección del estado de permisos
5. entrega:
   - diseño
   - código
   - ejemplos
   - tests
   - checklist de validación

---

## Prompt maestro Fase 4
Actúa como Bash Engineer + Platform Operator.

Objetivo:
integrar el control de capacidades de OpenClaw en la DAVLOS VPN Console.

Tareas:
1. amplía el menú de consola para mostrar capacidades activas
2. añade acciones para:
   - permitir
   - permitir con TTL
   - revocar
   - cerrar temporales
   - ver auditoría
3. mantén compatibilidad con el modo readonly actual
4. no añadas acciones peligrosas no pedidas
5. entrega:
   - diff
   - flujos de menú
   - ejemplos de uso
   - validaciones

Restricciones:
- no exponer secretos
- no romper la consola actual
- no tocar n8n ni Verity

---

## Prompt maestro Fase 5 Chat
Actúa como Full-Stack / Integration Engineer.

Objetivo:
diseñar el primer canal de chat para operar con OpenClaw usando el broker restringido.

Tareas:
1. proponer canal inicial más seguro para el VPS DAVLOS
2. definir autenticación, autorización y flujo de mensajes
3. hacer que el canal invoque acciones por ID, nunca comandos arbitrarios
4. registrar auditoría
5. entregar:
   - propuesta técnica
   - componentes
   - riesgos
   - MVP recomendado
   - plan de implementación

---

## Prompt maestro Fase 5 Telegram
Actúa como Integration Engineer.

Objetivo:
añadir Telegram privado como canal adicional para OpenClaw sin romper el aislamiento.

Tareas:
1. diseñar integración de bot privado
2. autenticar usuarios permitidos
3. mapear comandos de Telegram a capacidades del broker
4. registrar auditoría
5. no exponer control host-side directo
6. entregar:
   - arquitectura
   - riesgos
   - mitigaciones
   - MVP concreto

---

## Prompt maestro Fase 6
Actúa como DevSecOps Engineer.

Objetivo:
pasar de la allowlist documental de `agents_net` a enforcement real.

Tareas:
1. proponer política mínima de egress para OpenClaw
2. permitir sólo destinos aprobados
3. mantener funcionamiento de inference-gateway
4. validar que OpenClaw no alcanza lo no permitido
5. entregar:
   - propuesta exacta
   - comandos/scripts
   - validaciones
   - rollback

---

## Prompt maestro Fase 7
Actúa como observability engineer.

Objetivo:
diseñar e implementar auditoría mínima útil del plano OpenClaw.

Tareas:
1. definir formato de logs
2. registrar eventos de permisos y acciones
3. integrarlo con la consola readonly
4. proponer búsquedas/resúmenes rápidos
5. entregar:
   - diseño
   - implementación
   - ejemplos
   - checklist

---

## 12. Riesgos principales

### Riesgo 1 — dar demasiado poder al agente
Mitigación:
- capacidades cerradas
- broker
- no shell arbitraria

### Riesgo 2 — confundir canal con permiso
Mitigación:
- Telegram/chat sólo son frontend
- permisos reales viven en policy store

### Riesgo 3 — acoplar demasiado OpenClaw a la red actual
Mitigación:
- planificar sustitución futura de `172.22.0.1` por endpoint más abstracto cuando toque

### Riesgo 4 — fuga de secretos por scripts/logs
Mitigación:
- revisar scripts
- no imprimir `docker inspect` completo si contiene env

### Riesgo 5 — deriva documental
Mitigación:
- una sola verdad operativa vigente
- marcar histórico vs vigente

---

## 13. Definición de éxito

Se considerará éxito cuando:

1. OpenClaw siga aislado en su zona.
2. No tenga acceso libre al host.
3. Las acciones operativas se controlen por capacidades.
4. La consola pueda abrir/cerrar capacidades.
5. El sistema funcione por chat o Telegram sin romper el aislamiento.
6. Todo quede auditado.
7. Verity, n8n y la base del VPS sigan intactos.

---

## 14. Próximo paso recomendado

Empezar por **Fase 0** con una intervención de repo y control-plane:

- alinear documentación
- cerrar contradicciones
- limpiar posibles fugas de secretos en scripts
- dejar la rama OpenClaw lista para consolidación

Una vez hecho eso, pasar a **Fase 2 (broker restringido)**, porque esa es la pieza que realmente permite que el agente sea útil sin romper la segmentación.
