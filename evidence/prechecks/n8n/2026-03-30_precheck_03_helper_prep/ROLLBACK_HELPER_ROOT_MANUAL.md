# Rollback manual del helper root-owned readonly

## Objetivo

Eliminar completamente el acceso adicional concedido a `devops` para auditoría de `n8n`.

## Comandos exactos

```bash
sudo rm -f /etc/sudoers.d/davlos-n8n-audit-readonly
sudo rm -f /usr/local/sbin/davlos-n8n-audit-readonly
sudo visudo -c
```

## Validación posterior

```bash
test ! -e /etc/sudoers.d/davlos-n8n-audit-readonly && echo SUDOERS_REMOVED
test ! -e /usr/local/sbin/davlos-n8n-audit-readonly && echo HELPER_REMOVED
sudo -n -l
```

Resultado esperado:

- el helper deja de existir
- el sudoers deja de existir
- `devops` vuelve al estado previo sin acceso adicional
