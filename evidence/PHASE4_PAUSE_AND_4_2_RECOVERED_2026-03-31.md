# Fase 4 en pausa y 4.2 recuperada

## fecha

2026-03-31

## situación resumida

Fase 4 sigue abierta pero en pausa operativa. La incidencia histórica de 4.2 quedó recuperada y el runtime actual de `n8n` está estable.

## estado por fases

- Fase 3: cerrada históricamente
- Fase 4: abierta y en pausa operativa
- 4.2: recuperada operativamente
- 4.3: preparada, no ejecutar

## hechos confirmados

- runtime actual de `n8n`: `compose-n8n-1`
- `127.0.0.1:5678` devuelve `HTTP/1.1 200 OK`
- `127.0.0.1:81` sigue operativo
- red válida: `verity_network`
- persistencia válida: `root_n8n_data`
- bind mount válido: `/opt/automation/n8n/local-files -> /files`
- UI accesible y workflows visibles
- `DB_POSTGRESDB_PASSWORD` actual autentica correctamente contra PostgreSQL
- baseline post-recuperación creada en `/opt/backups/n8n/20260331T091708Z_post_recovery_baseline`

## conclusión técnica

La desalineación histórica de 4.2 no sigue activa. El estado operativo actual está recuperado y alineado con la topología post-migración bajo `/opt`.

## riesgos residuales

- el helper readonly estaba desfasado respecto al runtime actual de `n8n`
- el `README` público del control-plane sigue describiendo un estado previo

## decisión operativa

No continuar hoy con nuevas rotaciones ni nuevas suboperaciones sobre `n8n`. Mantener Fase 4 en pausa controlada.

## siguiente paso exacto

Dejar commit local con esta trazabilidad mínima y con el helper readonly ajustado al runtime actual.
