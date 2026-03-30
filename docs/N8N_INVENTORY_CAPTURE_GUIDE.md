# Guía de captura de inventario de workflows e integraciones de n8n

## Propósito

Esta guía explica cómo usar la plantilla documental de inventario para capturar, de forma prudente y sin exponer información sensible, los workflows e integraciones de `n8n`.

Su alcance es documental.
No ejecuta migraciones.
No autoriza cambios en servicios.
No sustituye validación técnica con evidencia real.

Plantilla asociada:

- `templates/N8N_WORKFLOW_AND_INTEGRATION_INVENTORY_TEMPLATE.md`

## Cómo usar la plantilla

- Crear una copia nueva de la plantilla por cada workflow que requiera seguimiento individual.
- Mantener un criterio consistente de nombrado y estado de inventario.
- Rellenar primero los campos que puedan confirmarse sin inspeccionar secretos.
- Registrar solo hechos observables, referencias trazables y notas prudentes.
- Si un dato no está confirmado, no inferirlo; marcarlo como `parcial` o `pendiente`.
- Usar referencias cruzadas mínimas solo cuando ayuden a relacionar dependencias o validaciones.

## Qué rellenar primero

Orden recomendado de captura:

1. Estado de inventario, fecha y responsable documental.
2. Identificación del workflow.
3. Trigger principal y patrón general de activación.
4. Integraciones externas observables.
5. Uso de archivos y dependencia de `local-files`.
6. Nivel de criticidad y justificación.
7. Referencias de credenciales, sin valores.
8. Dependencias previas.
9. Validación funcional esperada.
10. Evidencias capturadas y riesgos.

Razón del orden:

- permite fijar primero identidad, alcance e impacto
- reduce riesgo de mezclar suposiciones con evidencia
- deja para el final lo que suele requerir más contraste documental

## Qué no debe copiarse nunca al repositorio

No debe copiarse nunca:

- secretos, contraseñas, tokens, API keys, certificados o cookies
- contenido de `/root/n8n.env`
- contenido exportado de credenciales de `n8n`
- payloads sensibles de webhooks
- datos personales o de clientes que aparezcan en ejecuciones
- contenido sensible de archivos ubicados en `/root/local-files`
- capturas que expongan valores secretos o datos operativos sensibles

Si una evidencia existe pero es sensible:

- registrar solo una referencia segura
- indicar responsable o sistema custodio
- evitar cualquier copia parcial que pueda revelar datos

## Cómo clasificar workflows por criticidad

### Criticidad alta

Usar `alta` cuando el workflow cumpla uno o más de estos criterios:

- su fallo interrumpe una operación crítica
- su fallo exige rollback o mitigación inmediata
- soporta integraciones externas esenciales
- procesa entradas cuya pérdida o retraso tenga impacto relevante

### Criticidad media

Usar `media` cuando:

- el workflow es importante pero existe tolerancia temporal al fallo
- hay alternativa manual o recuperación razonable
- el impacto es acotado y no bloquea toda la operación

### Criticidad baja

Usar `baja` cuando:

- el workflow es accesorio, de soporte o laboratorio
- su fallo no compromete continuidad operativa principal
- puede reejecutarse o reconstruirse con bajo impacto

### Pendiente de clasificar

Usar `pendiente de clasificar` cuando todavía no exista evidencia suficiente para asignar impacto real.

## Cómo clasificar integraciones

Clasificar cada integración con dos ejes mínimos:

- tipo de integración
- dirección del flujo

Tipos sugeridos:

- `API`
- `webhook`
- `correo`
- `mensajería`
- `base de datos`
- `storage`
- `archivo`
- `servicio interno`
- `otro`

Dirección sugerida:

- `entrante`
- `saliente`
- `bidireccional`

Clasificación complementaria útil:

- criticidad de la integración
- si depende de credencial
- si depende de archivo local
- si la evidencia es confirmada, parcial o pendiente

## Qué evidencias mínimas recoger

Cada ficha debería reunir, como mínimo, evidencia suficiente para sostener estas preguntas:

- qué workflow es
- cómo se dispara
- con qué sistemas interactúa
- si depende de archivos locales
- qué validación funcional mínima se espera

Evidencias mínimas recomendadas:

- nombre e identificador del workflow, si son observables
- tipo de trigger principal
- lista resumida de integraciones externas relevantes
- referencia documental de credenciales usadas, sin valores
- indicación de uso o no uso de `local-files`
- criterio observable de éxito funcional
- fecha, responsable y fuente de la captura

## Estado de inventario recomendado

Usar `confirmado` cuando:

- la mayor parte de los bloques clave tiene evidencia suficiente
- no quedan dudas relevantes sobre trigger, integraciones y validación funcional mínima

Usar `parcial` cuando:

- existen hechos confirmados, pero faltan piezas relevantes
- todavía no puede sostenerse un inventario completo del workflow

Usar `pendiente` cuando:

- solo existe una referencia inicial o evidencia demasiado débil
- no pueden confirmarse todavía identidad, trigger o dependencias principales

## Referencias cruzadas mínimas útiles

Usar solo las necesarias para orientar la captura:

- `docs/N8N_FUNCTIONAL_DEPENDENCIES.md`
- `runbooks/N8N_MIGRATION_PREP.md`
- `runbooks/N8N_POST_MIGRATION_VALIDATION.md`

No conviene sobrecargar cada ficha con referencias que no aporten validación o contexto operativo.

## Criterio de calidad documental

Una ficha de inventario está en buen estado cuando:

- distingue hechos confirmados de datos pendientes
- no contiene secretos ni valores sensibles
- permite entender impacto, trigger, integraciones y validación esperada
- deja trazabilidad de evidencia y responsable
- puede reutilizarse en fases posteriores de validación o migración

## Siguiente uso recomendado

Una vez creada la ficha de un workflow, el siguiente paso prudente es revisar si:

- la criticidad está razonablemente clasificada
- las integraciones principales están identificadas
- existe dependencia de archivos o de rutas locales
- la validación funcional mínima está descrita de forma verificable

Si alguno de esos puntos falta, el estado debería mantenerse como `parcial` o `pendiente`.
