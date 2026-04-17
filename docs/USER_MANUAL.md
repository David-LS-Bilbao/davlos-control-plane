# Manual de usuario — OpenClaw Telegram Bot

OpenClaw es un bot de Telegram que actúa como interfaz de operación y chat sobre un vault Obsidian. Permite leer notas, escribir borradores, explorar secciones del vault y ejecutar acciones de sistema desde el móvil, con confirmación humana antes de toda mutación.

## Inicio rápido

1. Abre el chat privado con tu bot en Telegram
2. Escribe cualquier mensaje para empezar
3. El bot reconoce lenguaje natural en español

---

## Comandos de sistema

| Comando | Descripción |
|---|---|
| `/health` | Estado de servicios (openclaw, inference gateway) |
| `/logs [stream]` | Últimas líneas del log del runtime |
| `/policy` | Estado de acciones habilitadas en la policy |

---

## Vault Obsidian — Lectura y exploración

### Ver secciones del vault

```
qué secciones hay
muéstrame el vault
explora el vault
```

### Explorar una sección

```
qué hay en Proyectos
lista notas de Recursos
ver carpeta Archivo
```

### Leer una nota

```
lee la nota MiNota
muéstrame MiProyecto.md
abre la nota Ideas sprint 6
```

### Buscar en el vault

```
busca reunión
busca sprint
busca notas sobre n8n
```

### Ver zonas del agente

```
zonas del agente
ver borradores
ver reportes
ver heartbeat
```

---

## Escritura y borradores

### Escribir un borrador directo (ADR-003)

Crea una entrada en `Agent/Inbox_Agent/STAGED_INPUT.md` y un borrador en `Agent/Drafts_Agent/`.

```
escribe borrador: <título> :: <contenido>
crea borrador: Ideas sprint 6 :: Aquí van los detalles del sprint
borrador: Reunión cliente :: Puntos tratados hoy
```

El bot pedirá confirmación antes de escribir. Responde `sí` o `no`.

> **Nota:** Solo puede haber un `STAGED_INPUT.md` activo. Si el pipeline anterior no lo ha procesado, el bot lo indica con un mensaje de conflicto.

### Escribir en inbox (captura rápida)

```
captura: título :: contenido
/inbox_write
```

### Promover a draft

```
promueve MiNota a draft
/draft_promote
```

### Heartbeat del agente

```
registra heartbeat
heartbeat del agente
```

---

## Operaciones de vault (CRUD)

### Crear nota

```
crea una nota titulada MiNota en Proyectos
nueva nota: Ideas para sprint 6 en Recursos
```

### Archivar nota

```
archiva MiNota
mueve MiNota al archivo
```

### Editar nota

```
añade a MiNota: nuevo texto al final
reemplaza contenido de MiNota: nuevo contenido completo
```

### Mover nota

```
mueve MiNota a Recursos
traslada MiNota a Proyectos
```

---

## Confirmaciones

Toda acción de escritura requiere confirmación explícita:

- Para confirmar: `sí`, `si`, `confirma`, `ok`, `dale`
- Para cancelar: `no`, `cancela`, `para`, `abort`

La confirmación expira pasados unos minutos de inactividad.

---

## Sandbox mode (chat libre con LLM local)

Activa un modo de conversación libre con el modelo `qwen2.5:3b` (Ollama local). El LLM tiene contexto del vault y puede ejecutar acciones vault directamente.

### Activar

```
activa modo libre
libera openclaw
sandbox on
modo agentico
```

### Desactivar

```
sal del sandbox
modo normal
sandbox off
vuelve al modo normal
```

### Funcionamiento en sandbox

- Mensajes enviados directamente al LLM local
- El LLM puede proponer acciones vault que el bot ejecuta
- Historial de sesión mantenido (hasta 6 turnos)
- Los artefactos pipeline (`STAGED_INPUT.md`, `REPORT_INPUT.md`) no aparecen en los listados

---

## Flujo completo de borrador

```
1. Usuario: "escribe borrador: Ideas sprint 6 :: Detalles del sprint"
2. Bot:     "Voy a crear un borrador... ¿Confirmas? (sí/no)"
3. Usuario: "sí"
4. Bot:     "Borrador creado. ruta: Agent/Drafts_Agent/20260417T161223Z_draft_..."
5. Vault:   STAGED_INPUT.md → procesado por pipeline obsi-claw
            Draft en Agent/Drafts_Agent/ con estado pending_human_review
6. Obsidian: Revisar y promover el borrador desde el cliente Obsidian
```

---

## Límites y notas operativas

- La operación de escritura requiere que el vault esté montado y accesible en el VPS
- `STAGED_INPUT.md` solo puede existir uno a la vez (ventana del pipeline)
- Las notas en `Agent/` son gestionadas por el pipeline; no editarlas manualmente
- El bot opera en el canal Telegram configurado en `allowed_chats` de la policy
- Audit log disponible en `/opt/automation/agents/openclaw/broker/audit/restricted_operator.jsonl`

---

## Resolución de problemas

| Error | Causa | Solución |
|---|---|---|
| `vault no configurado` | `vault_root` vacío en policy | Configurar la ruta del vault en la policy |
| `conflict: STAGED_INPUT.md ya existe` | Pipeline anterior sin procesar | Esperar a que el agente lo procese o archivarlo en `_staging_backup/` |
| `action_id is unknown` | Acción no registrada en policy | Verificar que la acción está en la policy y reiniciar el servicio |
| `forbidden` | Acción deshabilitada | Habilitar la acción en la policy y reiniciar |
| `vault_root no configurado` | Falta `vault_inbox.vault_root` | Configurar en la policy y reiniciar |
