# OpenClaw Agents Net Reachability Fix 2026-04-01

## objetivo

Cerrar la reachability real `agents_net -> 172.22.0.1:11440` con el cambio mínimo y seguro, sin reabrir exposición pública en `inference-gateway`.

## estado inicial reconfirmado

### inference-gateway host-side

Correcto al inicio de esta intervención:

- `127.0.0.1:11440` en escucha
- `172.22.0.1:11440` en escucha
- `127.0.0.1:11440/healthz` responde
- `172.22.0.1:11440/healthz` responde
- `inference-gateway.service` activo

### OpenClaw / agents_net

Correcto al inicio:

- `openclaw-gateway` en `running/healthy`
- `netmode=agents_net`
- `agents_net` con:
  - `subnet=172.22.0.0/16`
  - `gateway=172.22.0.1`

### fallo inicial

Fallaba de forma repetible:

- `nc -vz 172.22.0.1 11440` desde el namespace de `openclaw-gateway`
- `fetch('http://172.22.0.1:11440/healthz')` desde el runtime Node de `openclaw-gateway`

Síntoma observado:

- `ConnectTimeoutError`
- reachability TCP/HTTP rota solo desde `agents_net`

## diagnóstico

### evidencia clave

`ufw status verbose` y `/etc/ufw/user.rules` declaraban reglas para:

- `172.22.0.0/16 -> 172.22.0.1:11440/tcp` en `br-0759beecc34d`

Pero la cadena efectiva cargada en runtime no las tenía:

- `iptables -vnL ufw-user-input --line-numbers`
- en runtime solo aparecía la excepción antigua para:
  - `172.19.0.0/16 -> 172.19.0.1:11434`
- no aparecía ninguna regla activa para:
  - `172.22.0.0/16 -> 172.22.0.1:11440`

Además:

- `/etc/ufw/ufw.conf` estaba en `ENABLED=no`
- `ufw status` reportaba `active`
- `ufw reload` devolvía `Firewall not enabled (skipping reload)`

### causa raíz exacta

Había una desalineación entre la configuración declarada de UFW y las reglas efectivamente cargadas en runtime:

- la regla necesaria para `agents_net -> 172.22.0.1:11440` existía en configuración
- pero no estaba materializada en la cadena efectiva `ufw-user-input`
- el tráfico desde `172.22.0.0/16` al puerto `11440` del host caía en `DROP` por la política de entrada

Conclusión:

- el timeout no era de bind
- el timeout no era de Docker network
- el timeout era de firewall runtime no alineado con la configuración declarada

## corrección mínima aplicada

Se aplicó solo una regla efectiva y estrecha en la cadena runtime:

```text
iptables -I ufw-user-input 8 \
  -i br-0759beecc34d \
  -p tcp \
  -s 172.22.0.0/16 \
  -d 172.22.0.1 \
  --dport 11440 \
  -j ACCEPT
```

Alcance exacto del cambio:

- origen: `172.22.0.0/16`
- interfaz: `br-0759beecc34d`
- destino: `172.22.0.1`
- puerto: `11440/tcp`
- sin tocar IP pública
- sin abrir otros puertos
- sin tocar otras aplicaciones

## evidencia después del cambio

### regla efectiva cargada

`iptables -vnL ufw-user-input | grep 11440` mostró:

- regla `ACCEPT` efectiva para `br-0759beecc34d`
- contador con tráfico real

### reachability desde agents_net

Correcto:

- `nc -vz 172.22.0.1 11440` desde el namespace de `openclaw-gateway`
- resultado:
  - `Connection to 172.22.0.1 11440 ... succeeded`

Correcto:

- `fetch('http://172.22.0.1:11440/healthz')` desde el runtime Node de `openclaw-gateway`
- resultado:
  - `status=200`

Correcto:

- contenedor efímero en `agents_net` contra `http://172.22.0.1:11440/healthz`
- resultado:
  - `200`

### host-side

Sigue correcto:

- `127.0.0.1:11440/healthz`
- `172.22.0.1:11440/healthz`

### OpenClaw

Sigue correcto:

- `http://127.0.0.1:18789/` devuelve HTML válido
- handshake WS mínimo devuelve `HTTP/1.1 101 Switching Protocols`

### IP pública

Sigue cerrado:

- `curl http://212.227.159.131:11440/healthz`
- resultado:
  - `curl: (7) Failed to connect`

## estado final de reachability

### logrado

- `openclaw-gateway` alcanza `172.22.0.1:11440`
- `agents_net` alcanza `172.22.0.1:11440`
- `inference-gateway` sigue sin responder por IP pública
- no se abrió más superficie de la necesaria

### riesgo residual

Existe drift operativo en UFW:

- `ufw.conf` sigue en `ENABLED=no`
- hay evidencia de diferencia entre reglas declaradas y reglas cargadas en runtime

Eso no bloquea la operación actual, pero sí merece una limpieza posterior para persistencia/reboot safety.

## decisión de fase

### decisión

`GO` para Fase 1 operativa del boundary de OpenClaw, con nota de seguimiento menor sobre normalización de UFW.

### justificación

El criterio funcional pedido para esta fase queda cumplido:

- OpenClaw alcanza el gateway de inferencia por la ruta prevista
- el gateway no expone `11440` por IP pública
- el cambio aplicado es mínimo, acotado y auditable

## artefactos tocados

Fuera del repo:

- runtime firewall host-side en cadena `ufw-user-input`

En el repo:

- `docs/reports/OPENCLAW_AGENTS_NET_REACHABILITY_FIX_2026-04-01.md`
