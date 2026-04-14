"""Tests for Phase 6 — Operational Hygiene and Conversational UX MVP.

Covers:
- vault_artifact_reader: read_pending_artifacts (presence detection, note name extraction)
- assistant_responses: Phase 6 render functions
- _match_obsidian_intent: Phase 6 intent detection (help, pending_artifacts, what_blocks)
- _handle_obsidian_intent: full flow for the 3 new sub-intents
- Improved error messages: staging_conflict, report_conflict, not_promotable, not_reportable
- Improved note status: created_at_utc + source_dir via get_note_status
- Improved ambiguous reference: numbered list + repeat example
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_OPENCLAW = Path(__file__).resolve().parents[2] / "scripts" / "agents" / "openclaw"
_RO = _OPENCLAW / "restricted_operator"

if str(_OPENCLAW) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW))
if str(_RO) not in sys.path:
    sys.path.insert(0, str(_RO))

from vault_artifact_reader import read_pending_artifacts, ArtifactStatus, STAGED_FILENAME, REPORT_FILENAME, INBOX_DIR  # noqa: E402
import assistant_responses  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

INBOX_SUBDIR = "Agent/Inbox_Agent"


def _note_content(
    *,
    run_id: str = "test-001",
    title: str = "Test Note",
    status: str = "pending_triage",
    created_at_utc: str = "2026-04-14T10:00:00Z",
) -> str:
    return (
        "---\n"
        f'run_id: "{run_id}"\n'
        f'capture_status: "{status}"\n'
        f'created_at_utc: "{created_at_utc}"\n'
        "---\n\n"
        f"# {title}\n\n"
        "Body.\n"
    )


def _make_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / INBOX_SUBDIR).mkdir(parents=True)
    return vault


def _write_note(inbox: Path, *, name: str, run_id: str = "r1", status: str = "pending_triage") -> Path:
    path = inbox / name
    path.write_text(_note_content(run_id=run_id, status=status), encoding="utf-8")
    return path


def _make_policy(root: Path, *, vault_root: str = "") -> Path:
    policy = {
        "broker": {
            "bind_host": "127.0.0.1",
            "bind_port": 18899,
            "audit_log_path": str(root / "audit.jsonl"),
            "state_store_path": str(root / "state.json"),
            "dropzone_dir": str(root / "dropzone"),
            "max_tail_lines": 20,
            "max_write_bytes": 4096,
        },
        "vault_inbox": {"vault_root": vault_root},
        "actions": {
            "action.inbox.write.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "inbox write",
            },
            "action.draft.promote.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "draft promote",
            },
            "action.report.promote.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "report promote",
            },
            "action.logs.read.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.read", "description": "logs read",
            },
        },
        "log_streams": {},
        "health_checks": {},
        "webhook_targets": {},
        "operator_auth": {
            "roles": {
                "viewer": ["policy.read"],
                "operator": ["policy.read", "operator.read", "operator.write", "operator.audit"],
            },
            "operators": {
                "op1": {"role": "operator", "active": True},
            },
        },
        "telegram": {
            "enabled": True,
            "api_base_url": "https://api.telegram.org",
            "bot_token_env": "TELEGRAM_BOT_TOKEN",
            "allowed_chats": {"100": {"principal_id": "p1", "operator_id": "op1"}},
            "allowed_users": {},
            "rate_limit_window_seconds": 60,
            "rate_limit_max_requests": 100,
            "max_command_length": 512,
            "poll_timeout_seconds": 30,
            "audit_tail_lines": 5,
            "offset_store_path": str(root / "offset.json"),
            "runtime_status_path": str(root / "status.json"),
        },
    }
    path = root / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# TestVaultArtifactReader
# ---------------------------------------------------------------------------

class TestVaultArtifactReader(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self._tmp.name))
        self.inbox = self.vault / INBOX_SUBDIR

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_no_artifacts(self) -> None:
        status = read_pending_artifacts(str(self.vault))
        self.assertFalse(status.staged_exists)
        self.assertFalse(status.report_exists)
        self.assertEqual(status.staged_note_name, "")
        self.assertEqual(status.report_note_name, "")

    def test_staged_exists(self) -> None:
        (self.inbox / STAGED_FILENAME).write_text("staged content", encoding="utf-8")
        status = read_pending_artifacts(str(self.vault))
        self.assertTrue(status.staged_exists)
        self.assertFalse(status.report_exists)

    def test_report_exists(self) -> None:
        (self.inbox / REPORT_FILENAME).write_text("report content", encoding="utf-8")
        status = read_pending_artifacts(str(self.vault))
        self.assertFalse(status.staged_exists)
        self.assertTrue(status.report_exists)

    def test_both_exist(self) -> None:
        (self.inbox / STAGED_FILENAME).write_text("staged", encoding="utf-8")
        (self.inbox / REPORT_FILENAME).write_text("report", encoding="utf-8")
        status = read_pending_artifacts(str(self.vault))
        self.assertTrue(status.staged_exists)
        self.assertTrue(status.report_exists)

    def test_note_name_extraction_from_frontmatter(self) -> None:
        content = (
            "---\n"
            'note_name: "20260414T100000Z_inbox_test.md"\n'
            "---\n"
            "body\n"
        )
        (self.inbox / STAGED_FILENAME).write_text(content, encoding="utf-8")
        status = read_pending_artifacts(str(self.vault))
        self.assertEqual(status.staged_note_name, "20260414T100000Z_inbox_test.md")

    def test_note_name_missing_returns_empty(self) -> None:
        (self.inbox / STAGED_FILENAME).write_text("no frontmatter here", encoding="utf-8")
        status = read_pending_artifacts(str(self.vault))
        self.assertTrue(status.staged_exists)
        self.assertEqual(status.staged_note_name, "")

    def test_nonexistent_vault_root(self) -> None:
        """Non-existent vault returns all False (is_file is False)."""
        status = read_pending_artifacts("/tmp/__nonexistent_vault__")
        self.assertFalse(status.staged_exists)
        self.assertFalse(status.report_exists)


# ---------------------------------------------------------------------------
# TestPhase6AssistantResponses
# ---------------------------------------------------------------------------

class TestPhase6AssistantResponses(unittest.TestCase):

    def test_render_error_staging_conflict_mentions_staged(self) -> None:
        msg = assistant_responses.render_error_staging_conflict("20260414T100000Z_inbox_test.md")
        self.assertIn("STAGED_INPUT.md", msg)
        self.assertIn("20260414T100000Z_inbox_test.md", msg)
        self.assertIn("artefactos pendientes", msg)

    def test_render_error_report_conflict_mentions_report(self) -> None:
        msg = assistant_responses.render_error_report_conflict("20260414T100000Z_inbox_test.md")
        self.assertIn("REPORT_INPUT.md", msg)
        self.assertIn("artefactos pendientes", msg)

    def test_render_error_not_promotable_gives_hint(self) -> None:
        msg = assistant_responses.render_error_not_promotable("my_note.md")
        self.assertIn("my_note.md", msg)
        self.assertIn("pending_triage", msg)
        self.assertIn("report", msg.lower())

    def test_render_error_not_reportable_gives_hint(self) -> None:
        msg = assistant_responses.render_error_not_reportable("my_note.md")
        self.assertIn("my_note.md", msg)
        self.assertIn("promoted_to_draft", msg)
        self.assertIn("draft", msg.lower())

    def test_render_error_note_not_found(self) -> None:
        msg = assistant_responses.render_error_note_not_found("bad-ref")
        self.assertIn("bad-ref", msg)
        self.assertIn("inbox", msg.lower())

    def test_render_obsidian_help_covers_main_intents(self) -> None:
        msg = assistant_responses.render_obsidian_help()
        for keyword in ("pending_triage", "report", "busca", "artefactos", "bloquea", "draft"):
            self.assertIn(keyword, msg, f"missing keyword: {keyword}")

    def test_render_pending_artifacts_no_artifacts(self) -> None:
        msg = assistant_responses.render_pending_artifacts(
            staged_exists=False, report_exists=False
        )
        self.assertIn("no hay artefacto", msg.lower())
        self.assertIn("No hay artefactos bloqueando", msg)

    def test_render_pending_artifacts_staged_present(self) -> None:
        msg = assistant_responses.render_pending_artifacts(
            staged_exists=True, report_exists=False, staged_note_name="my_note.md"
        )
        self.assertIn("STAGED_INPUT.md: PRESENTE", msg)
        self.assertIn("my_note.md", msg)

    def test_render_pending_artifacts_both_present(self) -> None:
        msg = assistant_responses.render_pending_artifacts(
            staged_exists=True, report_exists=True
        )
        self.assertIn("STAGED_INPUT.md: PRESENTE", msg)
        self.assertIn("REPORT_INPUT.md: PRESENTE", msg)

    def test_render_what_blocks_pending_triage(self) -> None:
        msg = assistant_responses.render_what_blocks("note.md", "pending_triage")
        self.assertIn("pending_triage", msg)
        self.assertIn("draft", msg.lower())
        self.assertIn("artefactos", msg.lower())

    def test_render_what_blocks_promoted_to_draft(self) -> None:
        msg = assistant_responses.render_what_blocks("note.md", "promoted_to_draft")
        self.assertIn("promoted_to_draft", msg)
        self.assertIn("report", msg.lower())

    def test_render_what_blocks_promoted_to_report(self) -> None:
        msg = assistant_responses.render_what_blocks("note.md", "promoted_to_report")
        self.assertIn("promoted_to_report", msg)
        self.assertIn("admite", msg.lower())

    def test_render_obsidian_ambiguous_numbered(self) -> None:
        candidates = ("note_a.md", "note_b.md", "note_c.md")
        msg = assistant_responses.render_obsidian_ambiguous(candidates, "promover a draft")
        self.assertIn("1.", msg)
        self.assertIn("2.", msg)
        self.assertIn("note_a.md", msg)
        self.assertIn("promover a draft", msg)
        # Should show repeat example
        self.assertIn("estado de note_a.md", msg)

    def test_render_obsidian_ambiguous_empty_candidates(self) -> None:
        msg = assistant_responses.render_obsidian_ambiguous((), "alguna acción")
        self.assertIn("Referencia ambigua", msg)

    def test_render_obsidian_note_status_v2_includes_source_dir(self) -> None:
        info = {
            "note_name": "20260414T100000Z_inbox_test.md",
            "run_id": "tg-001",
            "capture_status": "pending_triage",
            "created_at_utc": "2026-04-14T10:00:00Z",
            "source_dir": "Agent/Inbox_Agent",
        }
        msg = assistant_responses.render_obsidian_note_status_v2(info)
        self.assertIn("Agent/Inbox_Agent", msg)
        self.assertIn("2026-04-14T10:00:00Z", msg)
        self.assertIn("pending_triage", msg)


# ---------------------------------------------------------------------------
# TestPhase6IntentDetection
# ---------------------------------------------------------------------------

class TestPhase6IntentDetection(unittest.TestCase):
    """Test _match_obsidian_intent detects Phase 6 intents correctly."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        vault = _make_vault(root)
        policy_path = _make_policy(root, vault_root=str(vault))
        self.processor = TelegramCommandProcessor(str(policy_path))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _detect(self, text: str) -> dict[str, Any] | None:
        normalized = self.processor._normalize_text(text)
        return self.processor._match_obsidian_intent(normalized=normalized, original_text=text)

    # obsidian.help
    def test_detect_obsidian_help_phrase1(self) -> None:
        intent = self._detect("qué puedes hacer con obsidian")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.help")

    def test_detect_obsidian_help_phrase2(self) -> None:
        intent = self._detect("ayuda obsidian")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.help")

    def test_detect_obsidian_help_vault(self) -> None:
        intent = self._detect("ayuda vault")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.help")

    # obsidian.pending_artifacts
    def test_detect_pending_artifacts_phrase1(self) -> None:
        intent = self._detect("qué artefactos pendientes hay")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.pending_artifacts")

    def test_detect_pending_artifacts_phrase2(self) -> None:
        intent = self._detect("hay artefactos pendientes")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.pending_artifacts")

    def test_detect_pending_artifacts_phrase3(self) -> None:
        intent = self._detect("que hay en cola")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.pending_artifacts")

    # obsidian.what_blocks
    def test_detect_what_blocks_la_ultima(self) -> None:
        intent = self._detect("qué bloquea la ultima")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.what_blocks")
        self.assertIn("ultima", intent["params"]["note_ref"])

    def test_detect_what_blocks_specific_note(self) -> None:
        intent = self._detect("qué bloquea 20260414T100000Z_inbox_test.md")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.what_blocks")

    def test_detect_what_blocks_no_ref_returns_none(self) -> None:
        """'que bloquea' with empty ref should not match."""
        intent = self._detect("que bloquea")
        # Falls through to no match (ref would be empty)
        if intent is not None:
            self.assertNotEqual(intent["intent"], "obsidian.what_blocks")

    # Phase 6 intents should not accidentally match Phase 4/5 phrases
    def test_que_tengo_pendiente_still_list_pending(self) -> None:
        intent = self._detect("que tengo pendiente")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.list_pending")

    def test_busca_still_search(self) -> None:
        intent = self._detect("busca algo importante")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.search_text")


# ---------------------------------------------------------------------------
# TestPhase6IntentHandling
# ---------------------------------------------------------------------------

class TestPhase6IntentHandling(unittest.TestCase):
    """Integration tests: _handle_obsidian_intent for Phase 6 sub-intents."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault = _make_vault(self.root)
        self.inbox = self.vault / INBOX_SUBDIR
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))
        self.processor = TelegramCommandProcessor(str(self.policy_path))
        self.chat_id = "100"
        self.user_id = "0"
        self.operator_id = "op1"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _dispatch(self, text: str) -> str:
        return self.processor.handle_text(
            chat_id=self.chat_id, user_id=self.user_id, text=text
        )

    # obsidian.help
    def test_help_response_covers_obsidian(self) -> None:
        reply = self._dispatch("ayuda obsidian")
        self.assertIn("obsidian", reply.lower())
        self.assertIn("draft", reply.lower())
        self.assertIn("report", reply.lower())

    # obsidian.pending_artifacts
    def test_pending_artifacts_no_artifacts(self) -> None:
        reply = self._dispatch("qué artefactos pendientes hay")
        self.assertIn("STAGED_INPUT.md", reply)
        self.assertIn("REPORT_INPUT.md", reply)
        self.assertIn("no hay", reply.lower())

    def test_pending_artifacts_staged_present(self) -> None:
        (self.inbox / STAGED_FILENAME).write_text("staged content", encoding="utf-8")
        reply = self._dispatch("qué artefactos pendientes hay")
        self.assertIn("STAGED_INPUT.md: PRESENTE", reply)

    def test_pending_artifacts_both_present(self) -> None:
        (self.inbox / STAGED_FILENAME).write_text("staged", encoding="utf-8")
        (self.inbox / REPORT_FILENAME).write_text("report", encoding="utf-8")
        reply = self._dispatch("hay artefactos pendientes")
        self.assertIn("STAGED_INPUT.md: PRESENTE", reply)
        self.assertIn("REPORT_INPUT.md: PRESENTE", reply)

    # obsidian.what_blocks — no notes in vault
    def test_what_blocks_no_notes(self) -> None:
        reply = self._dispatch("qué bloquea la ultima")
        # Vault has no notes → "no hay notas" or similar safe response
        self.assertTrue(
            "no hay" in reply.lower() or "vault" in reply.lower() or "inbox" in reply.lower(),
            f"unexpected reply: {reply}",
        )

    # obsidian.what_blocks — with a note present
    def test_what_blocks_pending_triage(self) -> None:
        _write_note(
            self.inbox,
            name="20260414T100000Z_inbox_mytest.md",
            status="pending_triage",
        )
        reply = self._dispatch("qué bloquea la ultima")
        self.assertIn("pending_triage", reply)
        self.assertIn("draft", reply.lower())

    def test_what_blocks_promoted_to_draft(self) -> None:
        _write_note(
            self.inbox,
            name="20260414T100000Z_inbox_mytest.md",
            status="promoted_to_draft",
        )
        reply = self._dispatch("qué bloquea la ultima")
        self.assertIn("promoted_to_draft", reply)
        self.assertIn("report", reply.lower())


# ---------------------------------------------------------------------------
# TestPhase6PromoteErrorMessages
# ---------------------------------------------------------------------------

class TestPhase6PromoteErrorMessages(unittest.TestCase):
    """Test _render_promote_error returns contextual messages for each code."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        vault = _make_vault(root)
        policy_path = _make_policy(root, vault_root=str(vault))
        self.processor = TelegramCommandProcessor(str(policy_path))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_staging_conflict_message(self) -> None:
        msg = self.processor._render_promote_error(
            note_name="my_note.md", code="staging_conflict", target="draft"
        )
        self.assertIn("STAGED_INPUT.md", msg)
        self.assertIn("my_note.md", msg)

    def test_report_conflict_message(self) -> None:
        msg = self.processor._render_promote_error(
            note_name="my_note.md", code="report_conflict", target="report"
        )
        self.assertIn("REPORT_INPUT.md", msg)

    def test_not_promotable_message(self) -> None:
        msg = self.processor._render_promote_error(
            note_name="my_note.md", code="not_promotable", target="draft"
        )
        self.assertIn("pending_triage", msg)
        self.assertIn("my_note.md", msg)

    def test_not_reportable_message(self) -> None:
        msg = self.processor._render_promote_error(
            note_name="my_note.md", code="not_reportable", target="report"
        )
        self.assertIn("promoted_to_draft", msg)
        self.assertIn("my_note.md", msg)

    def test_not_found_message(self) -> None:
        msg = self.processor._render_promote_error(
            note_name="ghost.md", code="not_found", target="draft"
        )
        self.assertIn("ghost.md", msg)
        self.assertIn("inbox", msg.lower())

    def test_unknown_code_fallback(self) -> None:
        msg = self.processor._render_promote_error(
            note_name="my_note.md", code="unexpected_error", target="draft"
        )
        self.assertIn("unexpected_error", msg)
        self.assertIn("draft", msg.lower())


# ---------------------------------------------------------------------------
# TestPhase6NoteStatusImproved
# ---------------------------------------------------------------------------

class TestPhase6NoteStatusImproved(unittest.TestCase):
    """Test that _obsidian_show_status now returns created_at_utc and source_dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault = _make_vault(self.root)
        self.inbox = self.vault / INBOX_SUBDIR
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))
        self.processor = TelegramCommandProcessor(str(self.policy_path))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_show_status_includes_created_at_utc(self) -> None:
        _write_note(
            self.inbox,
            name="20260414T100000Z_inbox_mytest.md",
            status="pending_triage",
        )
        reply = self.processor.handle_text(
            chat_id="100",
            user_id="0",
            text="estado de 20260414T100000Z_inbox_mytest.md",
        )
        self.assertIn("2026-04-14T10:00:00Z", reply)

    def test_show_status_includes_source_dir(self) -> None:
        _write_note(
            self.inbox,
            name="20260414T100000Z_inbox_mytest.md",
            status="pending_triage",
        )
        reply = self.processor.handle_text(
            chat_id="100",
            user_id="0",
            text="estado de 20260414T100000Z_inbox_mytest.md",
        )
        self.assertIn("Agent/Inbox_Agent", reply)

    def test_show_status_not_found_is_conversational(self) -> None:
        reply = self.processor.handle_text(
            chat_id="100",
            user_id="0",
            text="estado de 20260414T100000Z_inbox_ghost.md",
        )
        # Should be a conversational not-found message, not a raw "Nota no encontrada: ..."
        self.assertIn("inbox", reply.lower())


if __name__ == "__main__":
    unittest.main()
