# Instalación manual del helper root-owned readonly

## Objetivo

Instalar un helper de auditoría de solo lectura para `n8n` sin conceder a `devops` acceso general a Docker ni a `/root`.

## Archivos de preparación

- `davlos-n8n-audit-readonly.sh`
- `davlos-n8n-audit-readonly.sudoers`

## Pasos exactos por root

### 1. Instalar el helper en la ruta final

```bash
sudo install -o root -g root -m 0750 \
  /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_03_helper_prep/davlos-n8n-audit-readonly.sh \
  /usr/local/sbin/davlos-n8n-audit-readonly
```

### 2. Instalar el sudoers restringido

```bash
sudo install -o root -g root -m 0440 \
  /opt/control-plane/evidence/prechecks/n8n/2026-03-30_precheck_03_helper_prep/davlos-n8n-audit-readonly.sudoers \
  /etc/sudoers.d/davlos-n8n-audit-readonly
```

### 3. Validar sintaxis de sudoers

```bash
sudo visudo -cf /etc/sudoers.d/davlos-n8n-audit-readonly
```

### 4. Validar permisos y ownership

```bash
ls -l /usr/local/sbin/davlos-n8n-audit-readonly
ls -l /etc/sudoers.d/davlos-n8n-audit-readonly
```

Esperado:

- helper: `root root` y modo `0750`
- sudoers: `root root` y modo `0440`

### 5. Validar desde `devops`

```bash
sudo -n -l
sudo -n /usr/local/sbin/davlos-n8n-audit-readonly docker_readonly
sudo -n /usr/local/sbin/davlos-n8n-audit-readonly inventory_minimum
```

## Validación funcional mínima

- el helper debe rechazar cualquier subcomando distinto de `docker_readonly` o `inventory_minimum`
- la salida de entorno debe mostrar solo nombres de variables
- no debe imprimirse ningún secreto ni payload

## No hacer

- no añadir `devops` al grupo `docker`
- no dar sudo directo a scripts del repo
- no permitir comodines en sudoers
