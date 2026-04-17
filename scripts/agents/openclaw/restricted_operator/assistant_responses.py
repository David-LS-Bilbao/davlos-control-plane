from __future__ import annotations

import json

from models import EffectiveActionState


def render_mutation_result(*, ok: bool, summary: str, action_id: str) -> str:
    if ok:
        return f"Acción aplicada.\n{summary}\naction_id={action_id}"
    return f"No se pudo aplicar la acción.\n{summary}\naction_id={action_id}"


def render_conversation_help() -> str:
    return (
        "No entendí la intención o no está soportada.\n"
        "Prueba una de estas frases:\n"
        "Sistema:\n"
        "- estado general\n"
        "- capacidades activas\n"
        "- auditoría reciente\n"
        "- logs openclaw 20\n"
        "- habilita / deshabilita action.<id>.v1\n"
        "Obsidian:\n"
        "- qué tengo pendiente\n"
        "- estado de la ultima\n"
        "- qué artefactos pendientes hay\n"
        "- qué bloquea la ultima\n"
        "- ayuda obsidian\n"
        "Si quieres hablar de forma más natural, usa /wake."
    )


def render_help(operator_id: str) -> str:
    return (
        f"operator={operator_id}\n"
        "\n"
        "Slash commands:\n"
        "/wake  /sleep  /status  /capabilities  /audit_tail\n"
        "/draft_promote [note=<nombre>]\n"
        "/report_promote [note=<nombre>]\n"
        "/execute <action_id> [k=v ...]\n"
        "\n"
        "Conversacional (sin /wake):\n"
        "- estado general | capacidades activas | auditoría reciente\n"
        "- qué tengo pendiente | qué está listo para report\n"
        "- estado de <nota o ref> | qué bloquea la ultima\n"
        "- qué artefactos pendientes hay\n"
        "- ayuda obsidian\n"
        "\n"
        "Modo asistente (/wake):\n"
        "- guarda esta idea: <título> :: <cuerpo>\n"
        "- promueve <ref> a draft | promueve <ref> a report\n"
        "- busca <texto> | muéstrame las últimas 5 notas\n"
        "- resúmeme lo guardado hoy"
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


def render_obsidian_note_status_v2(info: dict) -> str:
    """Phase 6 improved status: includes source_dir and created_at_utc."""
    lines = [
        f"nota: {info['note_name']}",
        f"run_id: {info.get('run_id', '?')}",
        f"estado: {info.get('capture_status', '?')}",
        f"creada: {info.get('created_at_utc', '?')}",
    ]
    if info.get("source_dir"):
        lines.append(f"directorio: {info['source_dir']}")
    return "\n".join(lines)


def render_obsidian_ambiguous(candidates: tuple[str, ...], action: str) -> str:
    """Phase 6 improved: numbered list + concrete repeat example."""
    if not candidates:
        return f"Referencia ambigua para {action}. Usa un nombre más específico."
    rows = "\n".join(f"  {i + 1}. {c}" for i, c in enumerate(candidates))
    first = candidates[0]
    return (
        f"Hay {len(candidates)} notas que coinciden. Sé más específico para {action}:\n"
        f"{rows}\n"
        f"Repite usando el nombre exacto del archivo. Ejemplo:\n"
        f"  estado de {first}"
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
        "\n"
        "Lectura:\n"
        "- qué tengo pendiente\n"
        "- qué está listo para report\n"
        "- estado de <nota o run_id>\n"
        "- qué bloquea la ultima\n"
        "- qué artefactos pendientes hay\n"
        "- muéstrame las últimas 5 notas\n"
        "- busca <texto>\n"
        "- resúmeme lo guardado hoy\n"
        "\n"
        "Escritura (con confirmación):\n"
        "- guarda esta idea: <título> :: <cuerpo>\n"
        "- promueve <ref> a draft\n"
        "- promueve <ref> a report\n"
        "- promueve la ultima a draft\n"
        "\n"
        "Ayuda: 'ayuda obsidian'\n"
        "Slash commands: /draft_promote, /report_promote, /inbox_write."
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


# ---------------------------------------------------------------------------
# Phase 6 — Operational Hygiene and Conversational UX renders
# ---------------------------------------------------------------------------

def render_error_staging_conflict(note_name: str) -> str:
    """Conversational error for staging_conflict code."""
    return (
        f"No puedo promover '{note_name}' a draft: ya hay un STAGED_INPUT.md pendiente.\n"
        "El pipeline anterior aún no ha procesado ese artefacto.\n"
        "Opciones:\n"
        "- Espera a que el pipeline consuma STAGED_INPUT.md.\n"
        "- Usa 'qué artefactos pendientes hay' para ver qué hay en cola."
    )


def render_error_report_conflict(note_name: str) -> str:
    """Conversational error for report_conflict code."""
    return (
        f"No puedo promover '{note_name}' a report: ya hay un REPORT_INPUT.md pendiente.\n"
        "El pipeline anterior aún no ha procesado ese artefacto.\n"
        "Opciones:\n"
        "- Espera a que el pipeline consuma REPORT_INPUT.md.\n"
        "- Usa 'qué artefactos pendientes hay' para ver qué hay en cola."
    )


def render_error_not_promotable(note_name: str) -> str:
    """Conversational error for not_promotable code."""
    return (
        f"No puedo promover '{note_name}' a draft.\n"
        "La nota no está en estado pending_triage.\n"
        "Pistas:\n"
        "- Si ya fue promovida a draft, usa 'promueve a report' o /report_promote.\n"
        "- Usa 'estado de <nota>' para ver su estado actual."
    )


def render_error_not_reportable(note_name: str) -> str:
    """Conversational error for not_reportable code."""
    return (
        f"No puedo promover '{note_name}' a report.\n"
        "La nota no está en estado promoted_to_draft.\n"
        "Pistas:\n"
        "- Si está en pending_triage, primero promuévela a draft.\n"
        "- Usa 'estado de <nota>' para ver su estado actual."
    )


def render_error_note_not_found(note_ref: str) -> str:
    """Conversational error when a note reference resolves to nothing."""
    return (
        f"No encontré ninguna nota que coincida con '{note_ref}' en el inbox.\n"
        "Prueba:\n"
        "- 'qué tengo pendiente' para ver las notas disponibles\n"
        "- Usa el nombre de archivo exacto con /draft_promote note=<nombre>"
    )


def render_obsidian_help() -> str:
    """Full capability list for Obsidian/vault conversational UX."""
    return (
        "Esto es lo que puedo hacer con Obsidian/vault:\n"
        "\n"
        "Lectura del vault (sin mutaciones):\n"
        "- 'qué tengo pendiente' — notas en pending_triage\n"
        "- 'qué está listo para report' — notas en promoted_to_draft\n"
        "- 'estado de <nota o ref>' — estado de una nota concreta\n"
        "- 'muéstrame las últimas 5 notas' — notas recientes\n"
        "- 'busca <texto>' — búsqueda por texto\n"
        "- 'resúmeme lo guardado hoy' — notas del día\n"
        "- 'qué artefactos pendientes hay' — STAGED/REPORT_INPUT.md en cola\n"
        "- 'qué bloquea la ultima' — por qué no se puede promover la última nota\n"
        "\n"
        "Escritura (requieren confirmación explícita):\n"
        "- 'guarda esta idea: <título> :: <cuerpo>' — nueva nota al inbox\n"
        "- 'promueve <ref> a draft' — promover a draft\n"
        "- 'promueve <ref> a report' — promover a report\n"
        "\n"
        "Slash commands equivalentes: /inbox_write /draft_promote /report_promote"
    )


def render_pending_artifacts(
    *,
    staged_exists: bool,
    report_exists: bool,
    staged_note_name: str = "",
    report_note_name: str = "",
) -> str:
    """Show pipeline artifact presence without revealing file content."""
    lines = ["Artefactos de pipeline en vault (solo lectura):"]
    if staged_exists:
        detail = f" (fuente: {staged_note_name})" if staged_note_name else ""
        lines.append(f"- STAGED_INPUT.md: PRESENTE{detail}")
        lines.append("  El pipeline de draft aún no ha consumido este artefacto.")
    else:
        lines.append("- STAGED_INPUT.md: no hay artefacto pendiente")
    if report_exists:
        detail = f" (fuente: {report_note_name})" if report_note_name else ""
        lines.append(f"- REPORT_INPUT.md: PRESENTE{detail}")
        lines.append("  El pipeline de report aún no ha consumido este artefacto.")
    else:
        lines.append("- REPORT_INPUT.md: no hay artefacto pendiente")
    if not staged_exists and not report_exists:
        lines.append("No hay artefactos bloqueando el pipeline.")
    return "\n".join(lines)


def render_wake_vault_context(
    *,
    pending_count: int | None,
    staged_exists: bool | None,
    report_exists: bool | None,
    last_event: str | None,
) -> str:
    """Concise vault summary appended to the /wake message."""
    lines = ["Vault:"]
    if pending_count is not None:
        lines.append(f"- pending_triage: {pending_count} nota(s)")
    if staged_exists is not None:
        staged = "PRESENTE" if staged_exists else "libre"
        report = "PRESENTE" if report_exists else "libre"
        lines.append(f"- STAGED_INPUT.md: {staged}  REPORT_INPUT.md: {report}")
    if last_event:
        lines.append(f"- último evento: {last_event}")
    if len(lines) == 1:
        return ""
    return "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 8 — Full vault CRUD renders
# ---------------------------------------------------------------------------

def render_vault_sections(sections: list) -> str:
    """E2 — list top-level vault sections."""
    if not sections:
        return "No encontré secciones en el vault."
    rows = [f"- {s.name}  ({s.note_count} nota(s))" for s in sections]
    return "Secciones del vault:\n" + "\n".join(rows)


def render_section_notes(folder: str, notes: list[str]) -> str:
    """E2 — list notes inside a vault section."""
    if not notes:
        return f"No hay notas en '{folder}'."
    rows = [f"- {n}" for n in notes[:30]]
    suffix = f"\n  … y {len(notes) - 30} más." if len(notes) > 30 else ""
    return f"Notas en {folder} ({len(notes)}):\n" + "\n".join(rows) + suffix


def render_note_content(note_name: str, rel_path: str, content: str, *, truncated: bool, total_lines: int) -> str:
    """E1 — show a note's content with truncation notice."""
    header = f"[{rel_path}]"
    body = content if content.strip() else "(nota vacía)"
    suffix = f"\n… ({total_lines} líneas en total, mostrando las primeras {total_lines if not truncated else 60})" if truncated else ""
    return f"{header}\n{body}{suffix}"


def render_note_ambiguous(candidates: list[tuple[str, object]], note_ref: str) -> str:
    """E1/E4 — note ref is ambiguous across whole vault."""
    rows = "\n".join(f"  {i + 1}. {rel}" for i, (rel, _) in enumerate(candidates[:8]))
    return (
        f"Hay {len(candidates)} notas que coinciden con '{note_ref}':\n"
        f"{rows}\n"
        "Usa la ruta completa. Ejemplo:\n"
        f"  muéstrame {candidates[0][0]}"
    )


def render_note_not_found_vault(note_ref: str) -> str:
    """E1/E4 — note not found anywhere in vault."""
    return (
        f"No encontré ninguna nota que coincida con '{note_ref}'.\n"
        "Prueba:\n"
        "- 'qué carpetas hay' para explorar el vault\n"
        "- 'busca <texto>' para búsqueda por contenido"
    )


def render_note_created(note_name: str, folder: str) -> str:
    """E3 — note created in any vault folder."""
    return f"Nota creada.\n{folder}/{note_name}"


def render_note_archived(note_name: str, from_path: str, to_path: str) -> str:
    """E4 — note moved to archive."""
    return f"Archivada.\n'{note_name}'\n{from_path} → {to_path}"


def render_what_blocks(note_name: str, capture_status: str) -> str:
    """Explain what blocks a note from its next promotion step."""
    if capture_status == "pending_triage":
        return (
            f"La nota '{note_name}' está en pending_triage.\n"
            "Puede promoverse a draft sin bloqueo de estado.\n"
            "Verifica también que no haya STAGED_INPUT.md en cola:\n"
            "  'qué artefactos pendientes hay'"
        )
    if capture_status == "promoted_to_draft":
        return (
            f"La nota '{note_name}' ya está en promoted_to_draft.\n"
            "Puede promoverse a report.\n"
            "Verifica que no haya REPORT_INPUT.md en cola:\n"
            "  'qué artefactos pendientes hay'"
        )
    if capture_status == "promoted_to_report":
        return (
            f"La nota '{note_name}' ya está en promoted_to_report.\n"
            "No admite más promociones desde este sistema."
        )
    return (
        f"La nota '{note_name}' tiene estado '{capture_status}'.\n"
        "No reconozco ese estado como parte del flujo estándar de este sistema."
    )


# ---------------------------------------------------------------------------
# Phase 9 — Sandbox mode renders
# ---------------------------------------------------------------------------

def render_sandbox_activated() -> str:
    return (
        "[SANDBOX] Modo libre activado.\n"
        "Tengo acceso completo al vault. Puedo leer, crear, archivar y gestionar notas.\n"
        "Todas las acciones quedan registradas en el audit log.\n"
        "Para salir: 'sal del sandbox' o 'modo normal'."
    )


def render_sandbox_deactivated() -> str:
    return "Modo libre desactivado. Volviendo al modo normal."


def render_sandbox_action_result(*, action_id: str, result: dict) -> str:
    return f"Acción ejecutada: {action_id}\n{json.dumps(result, ensure_ascii=False, indent=2)}"


def render_sandbox_action_error(*, action_id: str, error: str, code: str) -> str:
    return f"Error ejecutando {action_id}.\ncode={code}\nerror={error}"


def render_note_edited(note_name: str, rel_path: str, mode: str) -> str:
    verb = "Texto añadido" if mode == "append" else "Nota reemplazada"
    return f"{verb}.\n{rel_path}"


def render_note_moved(note_name: str, from_path: str, to_path: str) -> str:
    return f"Nota movida.\nde: {from_path}\na:  {to_path}"


def render_draft_written(draft_name: str, draft_rel: str, title: str) -> str:
    return (
        f"Borrador creado.\n"
        f"título: {title}\n"
        f"ruta: {draft_rel}\n"
        "Estado: pending_human_review — revísalo en Obsidian antes de promoverlo."
    )


def render_draft_write_confirm(title: str, body: str) -> str:
    preview = body[:100] + ("…" if len(body) > 100 else "")
    return (
        f"Voy a crear un borrador en Agent/Drafts_Agent.\n"
        f"título: {title}\n"
        f"contenido: {preview}\n"
        "¿Confirmas? (sí/no)"
    )


def render_draft_write_conflict() -> str:
    return (
        "No puedo crear el borrador: ya existe un STAGED_INPUT.md pendiente.\n"
        "Espera a que el pipeline lo procese o archívalo antes de continuar."
    )


def render_heartbeat_written(note_name: str, rel_path: str, heartbeat_type: str) -> str:
    return f"Heartbeat registrado.\ntipo: {heartbeat_type}\nruta: {rel_path}"


def render_heartbeat_confirm(heartbeat_type: str, context: str) -> str:
    preview = context[:80] + ("…" if len(context) > 80 else "")
    return (
        f"Voy a escribir un heartbeat '{heartbeat_type}' en Agent/Heartbeat.\n"
        f"Contexto: {preview}\n"
        "¿Confirmas? (sí/no)"
    )
