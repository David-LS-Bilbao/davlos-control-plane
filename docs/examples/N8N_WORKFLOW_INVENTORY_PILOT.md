# Ficha piloto de inventario de workflow e integración de n8n

## Nota inicial

Esta ficha es una ficha piloto.
No representa todavía un workflow confirmado de `n8n`.
Su propósito es validar que el formato documental definido en la plantilla resulta usable antes de capturar evidencia real.

## Propósito

Esta ficha piloto sirve para probar la estructura documental de inventario para un workflow de `n8n` y sus dependencias funcionales asociadas.

Su objetivo en esta fase es verificar que los bloques de captura permiten documentar identidad, criticidad, triggers, integraciones, dependencias y validación funcional sin incluir datos sensibles.

Esta ficha no ejecuta cambios.
Esta ficha no autoriza migraciones.
Esta ficha no sustituye evidencia real.

## Instrucciones de uso

- Usar esta ficha como ejemplo de formato, no como evidencia operativa.
- Sustituir cada marcador `pendiente de evidenciar` solo cuando exista soporte documental o evidencia verificable.
- Mantener el estado en `parcial` hasta que trigger, integraciones, dependencias y validación funcional tengan evidencia suficiente.
- No copiar secretos, valores de variables de entorno, credenciales exportadas ni contenido sensible de archivos locales.

## Reglas de seguridad documental

- No incluir secretos, tokens, contraseñas, API keys, cookies, certificados ni payloads sensibles.
- No copiar contenido de `/root/n8n.env`.
- No copiar contenido sensible de archivos asociados a `/root/local-files`.
- No registrar valores reales de credenciales; solo referencias neutras.
- Si una evidencia fuera sensible, registrar únicamente referencia segura y responsable de custodia.

## Estado de inventario

- Estado actual: `parcial`
- Fecha de captura: `2026-03-30`
- Última revisión: `2026-03-30`
- Responsable documental: `pendiente de evidenciar`

## Identificación del workflow

- Nombre visible del workflow: `workflow piloto para validación documental`
- ID interno de `n8n`: `pendiente de evidenciar`
- Estado observado: `no confirmado`
- Carpeta, proyecto o agrupación lógica: `pendiente de evidenciar`
- Descripción funcional breve:
  - ejemplo neutro para validar formato; la función real queda pendiente de evidenciar
- Fuente de evidencia utilizada:
  - plantilla base y guía de captura del control-plane
- Referencias cruzadas mínimas:
  - `templates/N8N_WORKFLOW_AND_INTEGRATION_INVENTORY_TEMPLATE.md`
  - `docs/N8N_INVENTORY_CAPTURE_GUIDE.md`

## Criticidad

- Nivel de criticidad: `pendiente de clasificar`
- Justificación de criticidad:
  - pendiente de evidenciar impacto operativo real
- Impacto si falla:
  - pendiente de evidenciar
- Impacto si no se ejecuta durante una ventana de cambio:
  - pendiente de evidenciar
- Requiere rollback inmediato si falla: `pendiente`
- Dependencia para procesos de negocio u operación interna:
  - pendiente de evidenciar

## Triggers

- Tipo de trigger principal: `pendiente de evidenciar`
- Trigger secundario o alternativo: `pendiente de evidenciar`
- Endpoint, evento o patrón de activación:
  - pendiente de evidenciar
  - no registrar secretos ni URLs sensibles
- Frecuencia esperada: `pendiente de evidenciar`
- Ventana horaria relevante: `pendiente de evidenciar`
- Dependencias de entrada previas al trigger: `pendiente de evidenciar`
- Observaciones sobre orden o secuencia de ejecución:
  - pendiente de evidenciar

## Integraciones externas

| Integración | Tipo | Dirección | Criticidad | Evidencia | Estado |
|---|---|---|---|---|---|
| `pendiente de evidenciar` | `pendiente de evidenciar` | `pendiente de evidenciar` | `pendiente de evidenciar` | `sin evidencia real en esta ficha piloto` | `parcial` |

Notas del bloque:

- La fila actual es un marcador estructural.
- Debe reemplazarse por sistemas reales solo cuando exista evidencia verificable.
- No registrar nombres de credenciales ni endpoints sensibles si no están validados para repositorio.

## Uso de archivos y `local-files`

- ¿El workflow depende de archivos locales?: `pendiente`
- Ruta observada o referencia funcional:
  - pendiente de evidenciar
- Tipo de uso: `pendiente de evidenciar`
- Descripción del uso:
  - pendiente de evidenciar
- Impacto si el archivo o ruta no existe:
  - pendiente de evidenciar
- Evidencia de uso capturada:
  - no disponible en esta ficha piloto
- Observaciones sobre sustitución futura de `/root/local-files`:
  - si existiera dependencia real, deberá documentarse sin copiar contenido sensible

## Credenciales

Este bloque es solo de referencia.
No registrar valores.

| Credencial o referencia | Tipo | Uso aparente | Ubicación o sistema de custodia | Estado |
|---|---|---|---|---|
| `referencia de credencial pendiente de evidenciar` | `pendiente de evidenciar` | `pendiente de evidenciar` | `n8n o sistema custodio, pendiente de evidenciar` | `parcial` |

Notas del bloque:

- Este ejemplo no contiene credenciales reales.
- El objetivo es validar que la referencia documental puede capturarse sin valores sensibles.

## Dependencias previas

- Servicios o sistemas que deben estar disponibles antes de ejecutar el workflow:
  - pendiente de evidenciar
- Archivos previos requeridos:
  - pendiente de evidenciar
- Datos previos requeridos:
  - pendiente de evidenciar
- Otros workflows previos requeridos:
  - pendiente de evidenciar
- Dependencias de red o resolución externa conocidas:
  - pendiente de evidenciar
- Dependencias aún no confirmadas:
  - trigger real
  - integraciones reales
  - dependencia de archivos locales
  - validación funcional mínima

## Validación funcional esperada

- Resultado funcional esperado:
  - pendiente de evidenciar
- Indicador observable de éxito:
  - pendiente de evidenciar
- Indicador observable de fallo:
  - pendiente de evidenciar
- Salida esperada del workflow:
  - pendiente de evidenciar
- Integraciones que deberían responder correctamente:
  - pendiente de evidenciar
- Evidencia mínima para considerar validación satisfactoria:
  - pendiente de evidenciar
- ¿Existe validación manual complementaria?: `pendiente`
- Notas de validación:
  - esta ficha piloto no valida comportamiento real; solo valida formato documental

## Evidencia capturada

| Tipo de evidencia | Fecha | Responsable | Ubicación o referencia | Sensible | Observaciones |
|---|---|---|---|---|---|
| `referencia documental interna` | `2026-03-30` | `equipo control-plane` | `templates/N8N_WORKFLOW_AND_INTEGRATION_INVENTORY_TEMPLATE.md` | `no` | `base estructural usada para la ficha piloto` |
| `referencia documental interna` | `2026-03-30` | `equipo control-plane` | `docs/N8N_INVENTORY_CAPTURE_GUIDE.md` | `no` | `guía usada para validar orden de captura y criterios` |
| `evidencia operativa real` | `pendiente de evidenciar` | `pendiente de evidenciar` | `pendiente de evidenciar` | `pendiente` | `bloque reservado para captura futura` |

Checklist mínimo de evidencia:

- [ ] Identificación básica del workflow confirmada
- [ ] Trigger principal identificado
- [ ] Integraciones principales identificadas
- [ ] Uso de archivos/local-files clasificado
- [ ] Referencias de credenciales documentadas sin valores
- [ ] Validación funcional esperada descrita

## Observaciones y riesgos

- Riesgos operativos conocidos:
  - esta ficha no debe usarse como evidencia de continuidad operativa
- Riesgos documentales:
  - si se reutiliza sin reemplazar los marcadores, puede inducir a falsa sensación de inventario avanzado
- Suposiciones pendientes de confirmar:
  - identidad real del workflow
  - trigger real
  - integraciones y dependencias reales
- Impacto probable de un cambio de layout:
  - pendiente de evidenciar
- Riesgos asociados a archivos locales:
  - si existiera dependencia de `local-files`, su omisión degradaría la utilidad de la ficha
- Riesgos asociados a integraciones externas:
  - sin evidencia real, no puede clasificarse impacto funcional
- Riesgos asociados a credenciales no inventariadas:
  - la validación futura seguiría siendo parcial

## Resumen final

- Clasificación final del inventario: `parcial`
- Motivo del estado final:
  - ficha piloto creada para validar estructura documental
  - no representa todavía un workflow confirmado
  - varios bloques permanecen como `pendiente de evidenciar`
- Próxima acción documental recomendada:
  - duplicar esta ficha o la plantilla base y sustituir primero identificación, trigger e integración principal con evidencia real no sensible
- Referencia a guía de captura:
  - `docs/N8N_INVENTORY_CAPTURE_GUIDE.md`
- Referencias contextuales mínimas:
  - `docs/N8N_FUNCTIONAL_DEPENDENCIES.md`
  - `runbooks/N8N_MIGRATION_PREP.md`
  - `runbooks/N8N_POST_MIGRATION_VALIDATION.md`
