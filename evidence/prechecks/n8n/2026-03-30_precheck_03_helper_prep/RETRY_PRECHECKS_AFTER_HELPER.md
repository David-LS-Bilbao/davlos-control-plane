# Reintento de prechecks tras instalar el helper

## Objetivo

Reintentar únicamente los pasos bloqueados del pack de prechecks después de instalar el helper root-owned readonly.

## Paso previo obligatorio

Validar primero:

```bash
sudo -n -l
sudo -n /usr/local/sbin/davlos-n8n-audit-readonly docker_readonly
sudo -n /usr/local/sbin/davlos-n8n-audit-readonly inventory_minimum
```

Si alguno falla, no continuar.

## Reintento recomendado

Ruta de evidencia sugerida:

- `/opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/`

Comandos:

```bash
mkdir -p /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04

/opt/control-plane/scripts/prechecks/n8n/30_n8n_docker_readonly.sh \
  > /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/30_n8n_docker_readonly.stdout.txt \
  2> /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/30_n8n_docker_readonly.stderr.txt

/opt/control-plane/scripts/prechecks/n8n/40_n8n_inventory_minimum.sh \
  > /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/40_n8n_inventory_minimum.stdout.txt \
  2> /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/40_n8n_inventory_minimum.stderr.txt
```

## Nota importante

Con el diseño actual del pack publicado, los scripts 30 y 40 siguen intentando `docker` directo o `sudo -n docker`.

Por tanto, para que el reintento funcione sin tocar privilegios amplios, debe hacerse una de estas dos cosas:

1. adaptar previamente los scripts 30 y 40 para que usen el helper si está presente
2. ejecutar directamente el helper y registrar su salida como evidencia equivalente

## Opción mínima recomendada

Sin cambiar aún los scripts publicados:

```bash
sudo -n /usr/local/sbin/davlos-n8n-audit-readonly docker_readonly \
  > /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/30_n8n_docker_readonly.stdout.txt \
  2> /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/30_n8n_docker_readonly.stderr.txt

sudo -n /usr/local/sbin/davlos-n8n-audit-readonly inventory_minimum \
  > /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/40_n8n_inventory_minimum.stdout.txt \
  2> /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_04/40_n8n_inventory_minimum.stderr.txt
```

## Siguiente mejora aconsejada

En una iteración posterior, adaptar de forma controlada:

- `scripts/prechecks/n8n/30_n8n_docker_readonly.sh`
- `scripts/prechecks/n8n/40_n8n_inventory_minimum.sh`

para soportar el helper root-owned como backend de lectura restringida.
