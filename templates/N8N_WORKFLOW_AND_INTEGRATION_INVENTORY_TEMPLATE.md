# Plantilla de inventario de workflow e integración de n8n

## Propósito

Esta plantilla sirve para documentar de forma prudente y trazable un workflow de `n8n` y sus dependencias funcionales asociadas.

Su objetivo es apoyar inventario, validación funcional, preparación de cambios futuros y captura de evidencia mínima.

Esta plantilla no ejecuta cambios.
Esta plantilla no autoriza migraciones.
Esta plantilla no sustituye verificación técnica con evidencia real.

## Instrucciones de uso

- Crear una copia por cada workflow relevante o, si resulta más útil, por cada workflow con una integración principal claramente diferenciada.
- Rellenar únicamente con hechos confirmados, observación directa o evidencia trazable.
- Si un dato no está confirmado, marcarlo como `pendiente` o `parcial`, sin inferir valores.
- Usar referencias internas al control-plane cuando exista soporte documental útil.
- Mantener redacción breve, verificable y orientada a operación.
- Actualizar la fecha de revisión y el responsable documental en cada iteración.

## Reglas de seguridad documental

- No incluir secretos, tokens, contraseñas, API keys, cookies, certificados, payloads sensibles ni valores de variables de entorno.
- No copiar contenido de credenciales exportadas desde `n8n`.
- No copiar contenido sensible de `/root/n8n.env`.
- No copiar contenido sensible de archivos en `/root/local-files` o su futura ruta equivalente.
- Si hace falta dejar constancia de una credencial o evidencia sensible, registrar solo referencia, ubicación controlada y responsable de custodia.

## Estado de inventario

- Estado actual: `confirmado | parcial | pendiente`
- Fecha de captura: `YYYY-MM-DD`
- Última revisión: `YYYY-MM-DD`
- Responsable documental: `nombre o rol`

## Identificación del workflow

- Nombre visible del workflow:
- ID interno de `n8n`:
- Estado observado:
  - `activo`
  - `inactivo`
  - `no confirmado`
- Carpeta, proyecto o agrupación lógica:
- Descripción funcional breve:
- Fuente de evidencia utilizada:
- Referencias cruzadas mínimas:

## Criticidad

- Nivel de criticidad:
  - `alta`
  - `media`
  - `baja`
  - `pendiente de clasificar`
- Justificación de criticidad:
- Impacto si falla:
- Impacto si no se ejecuta durante una ventana de cambio:
- Requiere rollback inmediato si falla:
  - `sí`
  - `no`
  - `pendiente`
- Dependencia para procesos de negocio u operación interna:

## Triggers

- Tipo de trigger principal:
  - `webhook`
  - `cron/schedule`
  - `manual`
  - `subworkflow`
  - `evento externo`
  - `otro`
- Trigger secundario o alternativo:
- Endpoint, evento o patrón de activación:
  - registrar solo nombre o referencia, nunca secretos
- Frecuencia esperada:
- Ventana horaria relevante:
- Dependencias de entrada previas al trigger:
- Observaciones sobre orden o secuencia de ejecución:

## Integraciones externas

| Integración | Tipo | Dirección | Criticidad | Evidencia | Estado |
|---|---|---|---|---|---|
| Nombre del sistema o servicio | API, webhook, correo, BD, storage, mensajería, archivo, otro | Entrante, saliente, bidireccional | Alta, media, baja, pendiente | Captura, nota, referencia documental | Confirmado, parcial, pendiente |

Notas del bloque:

- Registrar una fila por sistema externo relevante.
- Si existen varias operaciones contra el mismo sistema, resumirlas sin incluir valores sensibles.
- Si la integración aún no está confirmada, mantener estado `parcial` o `pendiente`.

## Uso de archivos y `local-files`

- ¿El workflow depende de archivos locales?
  - `sí`
  - `no`
  - `pendiente`
- Ruta observada o referencia funcional:
  - usar ruta o alias documental, sin copiar contenido sensible
- Tipo de uso:
  - `entrada`
  - `salida`
  - `temporal/intermedio`
  - `script auxiliar`
  - `adjunto`
  - `otro`
- Descripción del uso:
- Impacto si el archivo o ruta no existe:
- Evidencia de uso capturada:
- Observaciones sobre sustitución futura de `/root/local-files`:

## Credenciales

Este bloque es solo de referencia.
No registrar valores.

| Credencial o referencia | Tipo | Uso aparente | Ubicación o sistema de custodia | Estado |
|---|---|---|---|---|
| Nombre lógico o etiqueta | API key, OAuth, SMTP, BD, token, otro | Qué integración o nodo la usa | `n8n`, gestor externo, variable de entorno, pendiente | Confirmado, parcial, pendiente |

Notas del bloque:

- Si no se conoce el nombre exacto de la credencial, usar descripción neutra.
- No copiar JSON exportado, secrets ni campos sensibles.

## Dependencias previas

- Servicios o sistemas que deben estar disponibles antes de ejecutar el workflow:
- Archivos previos requeridos:
- Datos previos requeridos:
- Otros workflows previos requeridos:
- Dependencias de red o resolución externa conocidas:
- Dependencias aún no confirmadas:

## Validación funcional esperada

- Resultado funcional esperado:
- Indicador observable de éxito:
- Indicador observable de fallo:
- Salida esperada del workflow:
- Integraciones que deberían responder correctamente:
- Evidencia mínima para considerar validación satisfactoria:
- ¿Existe validación manual complementaria?
  - `sí`
  - `no`
  - `pendiente`
- Notas de validación:

## Evidencia capturada

| Tipo de evidencia | Fecha | Responsable | Ubicación o referencia | Sensible | Observaciones |
|---|---|---|---|---|---|
| Captura, nota, export parcial no sensible, referencia cruzada, ticket, runbook, otro | YYYY-MM-DD | nombre o rol | Ruta documental o referencia segura | Sí o no | Breve contexto |

Checklist mínimo de evidencia:

- [ ] Identificación básica del workflow confirmada
- [ ] Trigger principal identificado
- [ ] Integraciones principales identificadas
- [ ] Uso de archivos/local-files clasificado
- [ ] Referencias de credenciales documentadas sin valores
- [ ] Validación funcional esperada descrita

## Observaciones y riesgos

- Riesgos operativos conocidos:
- Riesgos documentales:
- Suposiciones pendientes de confirmar:
- Impacto probable de un cambio de layout:
- Riesgos asociados a archivos locales:
- Riesgos asociados a integraciones externas:
- Riesgos asociados a credenciales no inventariadas:

## Resumen final

- Clasificación final del inventario:
  - `confirmado`
  - `parcial`
  - `pendiente`
- Motivo del estado final:
- Próxima acción documental recomendada:
- Referencia a guía de captura:
  - `docs/N8N_INVENTORY_CAPTURE_GUIDE.md`
