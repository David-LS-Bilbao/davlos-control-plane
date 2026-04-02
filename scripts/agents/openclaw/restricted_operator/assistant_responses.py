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
    lines = ["Lectura rápida del estado actual:"]
    if not disabled and not consumed and not expired:
        lines.append("- No veo bloqueos inmediatos en policy.")
    if disabled:
        lines.append(f"- Hay capacidades deshabilitadas: {', '.join(disabled[:3])}")
    if expired:
        lines.append(f"- Hay capacidades expiradas: {', '.join(expired[:3])}")
    if consumed:
        lines.append(f"- Hay one-shot consumidas: {', '.join(consumed[:3])}")
    lines.append(f"- Operador en sesión: {operator_id}.")
    lines.append("- Si quieres, puedo proponerte una acción segura dentro de permisos.")
    return "\n".join(lines)


def render_assistant_suggestion(*, operator_id: str, states: list[EffectiveActionState]) -> str:
    for state in states:
        if state.status == "consumed":
            return (
                "Propuesta: revisar si conviene resetear el one-shot consumido.\n"
                f"Ejemplo: resetea one-shot {state.action_id}"
            )
        if state.status in {"disabled", "expired"}:
            return (
                "Propuesta: revisar si conviene habilitar temporalmente una capacidad hoy no disponible.\n"
                f"Ejemplo: habilita {state.action_id} por 15 minutos"
            )
    return (
        f"No veo una mutación urgente para {operator_id}. "
        "La policy parece estable; puedes pedirme estado, capacidades, auditoría o logs."
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
