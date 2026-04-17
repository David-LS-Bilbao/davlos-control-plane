# Guía de instalación — DAVLOS Control-Plane / OpenClaw Telegram Bot

## Requisitos previos

- Ubuntu 22.04+ / Debian 12+ en VPS
- Python 3.10+
- `systemd`
- Telegram Bot Token (obtenido via [@BotFather](https://t.me/BotFather))
- Obsidian vault sincronizado vía Syncthing en el VPS (opcional, para funciones vault)
- Ollama con modelo `qwen2.5:3b` (opcional, para sandbox mode)

## 1. Clonar el repositorio

```bash
git clone git@github.com:David-LS-Bilbao/davlos-control-plane.git /opt/control-plane
```

## 2. Dependencias Python

```bash
pip3 install requests
```

No hay dependencias adicionales: el bot usa únicamente la librería estándar de Python más `requests` para las llamadas HTTP a Telegram.

## 3. Estructura de directorios en producción

```
/opt/automation/agents/openclaw/
├── broker/
│   ├── restricted_operator_policy.json   ← policy activa (runtime)
│   ├── audit/restricted_operator.jsonl   ← audit log
│   └── state/restricted_operator_state.json
├── dropzone/                              ← zona de escritura controlada
└── logs/openclaw-current.log

/opt/data/obsidian/vault-main/            ← vault Obsidian (Syncthing)
│   ├── Agent/
│   │   ├── Inbox_Agent/
│   │   ├── Drafts_Agent/
│   │   ├── Reports_Agent/
│   │   └── Heartbeat/
│   └── ...                               ← carpetas de usuario

/etc/davlos/secrets/openclaw/
└── telegram-bot.env                      ← secretos (no en repo)
```

Crear directorios:

```bash
sudo mkdir -p /opt/automation/agents/openclaw/{broker/{audit,state},dropzone,logs}
sudo chown -R root:root /opt/automation/agents/openclaw
sudo chmod 700 /opt/automation/agents/openclaw
```

## 4. Configurar secretos

```bash
sudo mkdir -p /etc/davlos/secrets/openclaw
sudo chmod 700 /etc/davlos/secrets/openclaw
```

Crear `/etc/davlos/secrets/openclaw/telegram-bot.env`:

```bash
OPENCLAW_TELEGRAM_BOT_TOKEN=<token-del-bot>
```

```bash
sudo chmod 600 /etc/davlos/secrets/openclaw/telegram-bot.env
```

## 5. Desplegar la policy

```bash
sudo cp /opt/control-plane/templates/openclaw/restricted_operator_policy.json \
    /opt/automation/agents/openclaw/broker/restricted_operator_policy.json
```

Editar la policy para configurar:
- `vault_inbox.vault_root` → ruta absoluta al vault Obsidian (p.ej. `/opt/data/obsidian/vault-main`)
- `telegram.allowed_chats` → ID real del chat privado con el bot
- `telegram.enabled` → `true`

```bash
sudo nano /opt/automation/agents/openclaw/broker/restricted_operator_policy.json
```

Para obtener el chat ID: habla con el bot en Telegram, luego:

```bash
curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool | grep chat
```

## 6. Instalar el servicio systemd

```bash
sudo cp /opt/control-plane/templates/openclaw/openclaw-telegram-bot.service \
    /etc/systemd/system/openclaw-telegram-bot.service
sudo systemctl daemon-reload
sudo systemctl enable openclaw-telegram-bot.service
sudo systemctl start openclaw-telegram-bot.service
```

## 7. Verificar

```bash
sudo systemctl status openclaw-telegram-bot.service
sudo journalctl -u openclaw-telegram-bot.service -f
```

Envía `/health` al bot desde Telegram. Debe responder con el estado de los servicios.

## 8. Vault Obsidian (opcional)

Para funciones de vault (borrador, inbox, exploración), el vault debe estar accesible en la ruta configurada en `vault_root`. Con Syncthing:

```bash
# Verificar que el vault es legible por el servicio (root)
ls /opt/data/obsidian/vault-main/Agent/
```

Las carpetas `Agent/Inbox_Agent/`, `Agent/Drafts_Agent/`, `Agent/Reports_Agent/` y `Agent/Heartbeat/` deben existir para las acciones correspondientes.

## 9. Sandbox mode / Ollama (opcional)

Instalar Ollama y el modelo local:

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:3b
```

El endpoint de inferencia debe estar en `http://127.0.0.1:11440/v1/chat/completions` (configurable en `sandbox_mode.inference_url` de la policy).

## Actualizar la policy sin reiniciar el servicio

Los cambios al fichero de policy son recogidos dinámicamente para estados runtime (habilitar/deshabilitar acciones). El servicio debe reiniciarse para cargar acciones nuevas:

```bash
sudo systemctl restart openclaw-telegram-bot.service
```

## Rollback

```bash
sudo systemctl stop openclaw-telegram-bot.service
sudo cp /opt/control-plane/templates/openclaw/restricted_operator_policy.json \
    /opt/automation/agents/openclaw/broker/restricted_operator_policy.json
sudo systemctl start openclaw-telegram-bot.service
```
