# Instalación manual del helper readonly de OpenClaw

## Objetivo

Instalar un helper root-owned de solo lectura para que la consola DAVLOS pueda inspeccionar el runtime real de OpenClaw, el broker y Telegram sin conceder a `devops` acceso general a `/opt/automation` ni a `root`.

## Archivos preparados

- [davlos-openclaw-readonly.sh](/opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh)
- [davlos-openclaw-readonly.sudoers](/opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sudoers)

## Qué expone el helper

- `runtime_summary`
- `broker_state_console`
- `broker_audit_recent`
- `telegram_runtime_status`

Los subcomandos son cerrados y sin parámetros libres. No dan shell, no aceptan rutas arbitrarias y no escriben en runtime.

## Pasos exactos por root

### 1. Instalar el helper en la ruta final

```bash
sudo install -o root -g root -m 0750 \
  /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sh \
  /usr/local/sbin/davlos-openclaw-readonly
```

### 2. Instalar el sudoers restringido

```bash
sudo install -o root -g root -m 0440 \
  /opt/control-plane/templates/openclaw/davlos-openclaw-readonly.sudoers \
  /etc/sudoers.d/davlos-openclaw-readonly
```

### 3. Validar sintaxis de sudoers

```bash
sudo visudo -cf /etc/sudoers.d/davlos-openclaw-readonly
```

### 4. Validar permisos y ownership

```bash
ls -l /usr/local/sbin/davlos-openclaw-readonly
ls -l /etc/sudoers.d/davlos-openclaw-readonly
```

Esperado:

- helper: `root root` y modo `0750`
- sudoers: `root root` y modo `0440`

### 5. Validar desde `devops`

```bash
sudo -n -l
sudo -n /usr/local/sbin/davlos-openclaw-readonly runtime_summary
sudo -n /usr/local/sbin/davlos-openclaw-readonly broker_state_console
sudo -n /usr/local/sbin/davlos-openclaw-readonly broker_audit_recent
sudo -n /usr/local/sbin/davlos-openclaw-readonly telegram_runtime_status
```

## Integración esperada en la consola

Después de instalarlo:

- `openclaw-capabilities` debe poder mostrar el estado efectivo vivo vía helper si el state store directo no es legible.
- `openclaw-capabilities-audit` debe poder leer auditoría reciente vía helper.
- `openclaw-telegram` debe poder mostrar `telegram_runtime_status.json` vía helper.
- `overview` y `openclaw-diagnostics` deben marcar el helper readonly como disponible.

## No hacer

- no añadir `devops` a grupos con acceso general a `/opt/automation`
- no dar sudo directo a scripts versionados del repo
- no permitir comodines en sudoers
- no ampliar este helper a acciones mutantes

## Rollback

```bash
sudo rm -f /etc/sudoers.d/davlos-openclaw-readonly
sudo rm -f /usr/local/sbin/davlos-openclaw-readonly
```

Comprobación:

```bash
test ! -e /etc/sudoers.d/davlos-openclaw-readonly && echo SUDOERS_REMOVED
test ! -e /usr/local/sbin/davlos-openclaw-readonly && echo HELPER_REMOVED
```
