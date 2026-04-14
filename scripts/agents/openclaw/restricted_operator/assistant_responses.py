from __future__ import annotations

from models import EffectiveActionState


def render_mutation_result(*, ok: bool, summary: str, action_id: str) -> str:
    if ok:
        return f"Acción aplicada.\n{summary}\naction_id={action_id}"
    return f"No se pudo aplicar la acción.\n{summary}\naction_id={action_id}"


def render_conversation_help() -> str:
    return (
        "No entendí la intención o no está soportada.\n"
        "Prueba una de estas frases:\n"
        "- estado general\n"
        "- capacidades activas\n"
        "- auditoría reciente\n"
        "- logs openclaw 20\n"
        "- habilita action.dropzone.write.v1\n"
        "- deshabilita action.dropzone.write.v1\n"
        "- habilita action.dropzone.write.v1 por 15 minutos\n"
        "- resetea one-shot action.webhook.trigger.v1\n"
        "Si quieres hablar de forma más natural, usa /wake."
    )


def render_help(operator_id: str) -> str:
    return (
        f"operator={operator_id}\n"
        "/wake\n"
        "/sleep\n"
        "/status\n"
        "/capabilities\n"
        "/audit_tail\n"
        "/execute <action_id> [k=v ...]\n"
        "Conversacional: estado general | capacidades activas | auditoría reciente | logs openclaw 20"
    )


def render_assistant_status(*, operator_id: str, total_actions: int, summary: dict[str, int]) -> str:
    return (
        "Estado general de OpenClaw:\n"
        f"- operador activo: {operator_id}\n"
        f"- capacidades totales: {total_actions}\n"
        f"- activas: {summary.get('enabled', 0)}\n"
        f"- deshabilitadas: {summary.get('disabled', 0)}\n"
        f"- expiradas: {summary.get('expired', 0)}\n"
        f"- one-shot consumidas: {summary.get('consumed', 0)}"
    )


def render_assistant_capabilities(*, rows: list[str]) -> str:
    return "Capacidades activas y visibles para este operador:\n" + (
        "\n".join(rows) if rows else "- no hay acciones configuradas"
    )


def render_assistant_audit_tail(body: str) -> str:
    return "Últimos eventos de auditoría que puedo mostrarte:\n" + body


def render_assistant_explanation(
    *,
    operator_id: str,
    disabled: list[str],
    expired: list[str],
    consumed: list[str],
) -> str:
    lines = [
        "Lectura prudente de los estados de capacidad:",
        "- enabled: la capacidad está disponible ahora mismo dentro de policy y permisos.",
        "- disabled: la capacidad está cerrada de forma explícita hasta que alguien la vuelva a habilitar.",
        "- expired: estuvo habilitada con tiempo limitado y ese plazo ya terminó.",
        "- consumed/one-shot: era de un solo uso y ya se gastó; no vuelve a correr hasta reset explícito.",
    ]
    if not disabled and not consumed and not expired:
        lines.append("- En este momento no veo señales de cierre o agotamiento en policy.")
    if disabled:
        lines.append(f"- Ahora mismo veo deshabilitadas: {', '.join(disabled[:3])}.")
    if expired:
        lines.append(f"- También veo expiradas: {', '.join(expired[:3])}.")
    if consumed:
        lines.append(f"- Y veo one-shot consumidas: {', '.join(consumed[:3])}.")
    lines.append(f"- Operador en sesión: {operator_id}.")
    lines.append("- Si quieres, puedo seguir con una lectura de auditoría, capacidades o logs permitidos.")
    return "\n".join(lines)


def render_assistant_suggestion(*, operator_id: str, states: list[EffectiveActionState]) -> str:
    disabled = [state.action_id for state in states if state.status == "disabled"]
    expired = [state.action_id for state in states if state.status == "expired"]
    consumed = [state.action_id for state in states if state.status == "consumed"]
    if disabled or expired or consumed:
        lines = [
            "Propuesta prudente:",
            "- primero revisar auditoría reciente para entender por qué cambió el estado.",
            "- después revisar capacidades activas/expiradas para confirmar el impacto real.",
            "- si hace falta más contexto, leer logs permitidos antes de tocar nada sensible.",
        ]
        if expired:
            lines.append(f"- Veo {len(expired)} capacidades expiradas; eso sugiere revisar si el TTL venció como estaba previsto.")
        if disabled:
            lines.append(f"- Veo {len(disabled)} capacidades deshabilitadas; lo prudente es confirmar si siguen debiendo estar cerradas.")
        if consumed:
            lines.append(f"- Veo {len(consumed)} one-shot consumidas; conviene verificar si ese consumo era esperado.")
        lines.append("- Solo si el contexto lo justifica tendría sentido plantear un cambio temporal o un reset explícito.")
        return "\n".join(lines)
    return (
        f"No veo una mutación urgente para {operator_id}. "
        "Lo prudente es seguir con auditoría, capacidades o logs permitidos antes de cambiar nada."
    )


def render_assistant_identity(*, operator_id: str) -> str:
    return (
        "Soy el asistente controlado de OpenClaw para DAVLOS Control-Plane.\n"
        f"Opero dentro de los permisos del operador {operator_id}.\n"
        "Puedo resumir estado, capacidades, auditoría, logs permitidos y proponerte acciones seguras.\n"
        "No ejecuto shell libre ni salgo del perímetro broker/policy."
    )


def render_assistant_fallback() -> str:
    return (
        "No puedo interpretar esa frase de forma segura.\n"
        "Puedo ayudarte con:\n"
        "- estado general\n"
        "- capacidades activas\n"
        "- auditoría reciente\n"
        "- logs openclaw 20\n"
        "- explica el estado\n"
        "- qué propones\n"
        "- habilita/deshabilita una capacidad concreta\n"
        "Para salir del modo asistente usa /sleep."
    )


# ---------------------------------------------------------------------------
# Phase 4 — Obsidian conversational layer renders
# ---------------------------------------------------------------------------

def render_obsidian_list(notes: list[dict], caption: str) -> str:
    if not notes:
        return f"No hay notas en estado {caption}."
    rows = [f"- {n['note_name']}  run_id={n['run_id']}  {n.get('created_at_utc', '?')}" for n in notes]
    return f"Notas {caption}:\n" + "\n".join(rows)


def render_obsidian_note_status(info: dict) -> str:
    return (
        f"nota: {info['note_name']}\n"
        f"run_id: {info['run_id']}\n"
        f"estado: {info['capture_status']}\n"
        f"creada: {info.get('created_at_utc', '?')}"
    )


def render_obsidian_ambiguous(candidates: tuple[str, ...], action: str) -> str:
    rows = "\n".join(f"- {c}" for c in candidates)
    return (
        f"Hay varias notas que coinciden con esa referencia.\n"
        f"Sé más específico para {action}:\n"
        f"{rows}\n"
        f"Usa el nombre de archivo exacto o un fragmento único del run_id."
    )


def render_obsidian_vault_not_configured() -> str:
    return "vault_inbox.vault_root no está configurado en la policy."


def render_obsidian_capture_clarify() -> str:
    return (
        "Para capturar una nota conversacionalmente usa el formato:\n"
        "  guarda esta idea: <título> :: <cuerpo>\n"
        "Ejemplo:\n"
        "  guarda esta idea: Plan de hoy :: Revisar costes del proyecto\n"
        "O usa el slash command: /inbox_write run_id=<id> title=<título> :: <cuerpo>"
    )


def render_obsidian_conversation_help() -> str:
    return (
        "Intenciones Obsidian disponibles:\n"
        "- qué tengo pendiente\n"
        "- qué está listo para report\n"
        "- estado de <nota o run_id>\n"
        "- guarda esta idea: <título> :: <cuerpo>\n"
        "- promueve <ref> a draft\n"
        "- promueve <ref> a report\n"
        "- promueve la ultima a draft\n"
        "- muéstrame las últimas 5 notas\n"
        "- busca <texto>\n"
        "- resúmeme lo guardado hoy\n"
        "Los slash commands siguen funcionando: /draft_promote, /report_promote, /inbox_write."
    )


# ---------------------------------------------------------------------------
# Phase 5 — Vault Read Chat renders
# ---------------------------------------------------------------------------

def render_vault_last_n(notes: list, n: int) -> str:
    """Render a list of recent notes."""
    if not notes:
        return "No hay notas recientes en el vault."
    rows = []
    for info in notes:
        label = info.source_dir.split("/")[-1]
        rows.append(f"- [{label}] {info.note_name}  estado={info.capture_status}")
        if info.title and info.title != info.note_name:
            rows.append(f"  título: {info.title[:60]}")
    return f"Últimas {len(notes)} nota(s):\n" + "\n".join(rows)


def render_vault_search(notes: list, query: str) -> str:
    """Render text search results."""
    if not notes:
        return f"No encontré notas con '{query}'."
    rows = []
    for info in notes:
        label = info.source_dir.split("/")[-1]
        rows.append(f"- [{label}] {info.note_name}")
        if info.title:
            rows.append(f"  título: {info.title[:60]}")
        if info.excerpt:
            rows.append(f"  …{info.excerpt[:80]}…")
    return f"Resultados para '{query}' ({len(notes)} nota(s)):\n" + "\n".join(rows)


def render_vault_summary_today(notes: list, today: str) -> str:
    """Render today's notes summary."""
    if not notes:
        return f"No hay notas guardadas hoy ({today})."
    rows = []
    for info in notes:
        rows.append(f"- {info.title[:50]}  estado={info.capture_status}")
    return f"Guardado hoy {today} — {len(notes)} nota(s):\n" + "\n".join(rows)
