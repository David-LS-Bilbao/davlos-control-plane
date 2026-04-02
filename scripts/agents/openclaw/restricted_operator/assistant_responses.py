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
