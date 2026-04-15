"""Tests for Phase 5 — Vault Conversational Read Chat MVP.

Coverage:
  - vault_read_chat module functions (list_last_n, search_notes, summarize_today)
  - Phase 5 intent detection (_match_obsidian_intent via _normalize_text)
  - Telegram handler integration (vault not configured, permission denied, results)
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import tempfile
import os

# Make the openclaw modules importable
_OPENCLAW = Path(__file__).resolve().parents[2] / "scripts" / "agents" / "openclaw"
if str(_OPENCLAW) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW))
_RO = _OPENCLAW / "restricted_operator"
if str(_RO) not in sys.path:
    sys.path.insert(0, str(_RO))

from vault_read_chat import (
    list_last_n,
    search_notes,
    summarize_today,
    NoteInfo,
    INBOX_DIR,
    REPORTS_DIR,
    READ_DIRS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault(tmp: str) -> tuple[Path, Path]:
    """Create a vault directory with Agent/Inbox_Agent and Agent/Reports_Agent."""
    inbox = Path(tmp) / "Agent" / "Inbox_Agent"
    reports = Path(tmp) / "Agent" / "Reports_Agent"
    inbox.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    return inbox, reports


def _note(dir_path: Path, name: str, *, run_id: str = "run-1",
          capture_status: str = "pending_triage",
          created_at_utc: str = "2026-04-14T10:00:00Z",
          title: str = "Test Title",
          body: str = "Body text here.") -> Path:
    """Write a minimal inbox note to dir_path."""
    content = (
        "---\n"
        f'run_id: "{run_id}"\n'
        f'capture_status: "{capture_status}"\n'
        f'created_at_utc: "{created_at_utc}"\n'
        f'capture_title: "{title}"\n'
        "---\n"
        f"# {title}\n\n"
        f"## Captura\n\n{body}\n"
    )
    p = dir_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _today_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# TestVaultReadChatListLastN
# ---------------------------------------------------------------------------

class TestVaultReadChatListLastN(unittest.TestCase):

    def test_empty_vault_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            result = list_last_n(tmp, 5)
            self.assertEqual(result, [])

    def test_returns_n_notes_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T120000Z_inbox_a.md", run_id="a", title="Alpha")
            _note(inbox, "20260414T130000Z_inbox_b.md", run_id="b", title="Beta")
            _note(inbox, "20260414T140000Z_inbox_c.md", run_id="c", title="Gamma")
            result = list_last_n(tmp, 2)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].run_id, "c")  # newest first
            self.assertEqual(result[1].run_id, "b")

    def test_n_clamped_to_max_10(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            for i in range(15):
                _note(inbox, f"20260414T{i:02d}0000Z_inbox_n{i}.md", run_id=f"r{i}")
            result = list_last_n(tmp, 99)
            self.assertLessEqual(len(result), 10)

    def test_reads_across_both_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, reports = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_i1.md", run_id="i1", title="Inbox note")
            _note(reports, "20260414T110000Z_report_r1.md", run_id="r1", title="Report note")
            result = list_last_n(tmp, 5)
            source_dirs = {n.source_dir for n in result}
            self.assertIn(INBOX_DIR, source_dirs)
            self.assertIn(REPORTS_DIR, source_dirs)

    def test_n_zero_returns_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_only.md", run_id="only")
            result = list_last_n(tmp, 0)
            self.assertEqual(len(result), 1)

    def test_note_fields_populated(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(
                inbox, "20260414T100000Z_inbox_fields.md",
                run_id="myrun", capture_status="pending_triage",
                title="My Title", body="Some content about verity.",
            )
            result = list_last_n(tmp, 1)
            self.assertEqual(len(result), 1)
            n = result[0]
            self.assertEqual(n.run_id, "myrun")
            self.assertEqual(n.capture_status, "pending_triage")
            self.assertEqual(n.title, "My Title")
            self.assertIn("verity", n.excerpt)


# ---------------------------------------------------------------------------
# TestVaultReadChatSearch
# ---------------------------------------------------------------------------

class TestVaultReadChatSearch(unittest.TestCase):

    def test_empty_vault_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_vault(tmp)
            self.assertEqual(search_notes(tmp, "verity"), [])

    def test_finds_by_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_a.md", title="Verity plan")
            _note(inbox, "20260414T110000Z_inbox_b.md", title="Other note")
            result = search_notes(tmp, "verity")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].title, "Verity plan")

    def test_finds_by_excerpt(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_a.md", title="Plan", body="mentions costes Q2")
            _note(inbox, "20260414T110000Z_inbox_b.md", title="Other", body="unrelated")
            result = search_notes(tmp, "costes")
            self.assertEqual(len(result), 1)

    def test_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_cs.md", title="COSTES Plan")
            result = search_notes(tmp, "costes")
            self.assertEqual(len(result), 1)

    def test_empty_query_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_x.md", title="Something")
            self.assertEqual(search_notes(tmp, ""), [])
            self.assertEqual(search_notes(tmp, "  "), [])

    def test_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_x.md", title="Alpha")
            self.assertEqual(search_notes(tmp, "zzznomatch"), [])

    def test_max_results_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            for i in range(15):
                _note(inbox, f"20260414T{i:02d}0000Z_inbox_n{i}.md",
                      title=f"Costes note {i}")
            result = search_notes(tmp, "costes", max_results=4)
            self.assertLessEqual(len(result), 4)


# ---------------------------------------------------------------------------
# TestVaultReadChatSummaryToday
# ---------------------------------------------------------------------------

class TestVaultReadChatSummaryToday(unittest.TestCase):

    def test_empty_vault_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_vault(tmp)
            self.assertEqual(summarize_today(tmp), [])

    def test_returns_notes_created_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            today = _today_prefix()
            # Today's note
            _note(
                inbox, f"{today}T100000Z_inbox_today.md",
                run_id="today-note",
                created_at_utc=f"{today[:4]}-{today[4:6]}-{today[6:]}T10:00:00Z",
            )
            # Old note (different date)
            _note(inbox, "20200101T100000Z_inbox_old.md", run_id="old-note")
            result = summarize_today(tmp)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].run_id, "today-note")

    def test_old_notes_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20200101T100000Z_inbox_past.md", run_id="past")
            _note(inbox, "20191231T120000Z_inbox_older.md", run_id="older")
            self.assertEqual(summarize_today(tmp), [])


# ---------------------------------------------------------------------------
# TestPhase5IntentDetection
# ---------------------------------------------------------------------------

class TestPhase5IntentDetection(unittest.TestCase):
    """Test _match_obsidian_intent detects Phase 5 intents correctly."""

    def _make_processor(self):
        from telegram_bot import TelegramCommandProcessor
        mock_api = MagicMock()
        mock_policy = MagicMock()
        mock_policy.telegram.rate_limit_window_seconds = 60
        mock_policy.telegram.rate_limit_max_requests = 30
        mock_policy.telegram.bot_token_env = "BOT_TOKEN"
        mock_policy.telegram.api_base_url = "https://api.telegram.org"
        mock_policy.telegram.max_command_length = 512
        proc = TelegramCommandProcessor.__new__(TelegramCommandProcessor)
        proc.policy = mock_policy
        return proc

    def _normalize(self, proc, text: str) -> str:
        return proc._normalize_text(text)

    def test_list_last_n_default(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "muéstrame las últimas 5 notas")
        result = proc._match_obsidian_intent(normalized=norm, original_text="muéstrame las últimas 5 notas")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.list_last_n")
        self.assertEqual(result["params"]["n"], 5)

    def test_list_last_n_different_count(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "últimas 3 notas")
        result = proc._match_obsidian_intent(normalized=norm, original_text="últimas 3 notas")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.list_last_n")
        self.assertEqual(result["params"]["n"], 3)

    def test_list_last_n_no_number_defaults_to_5(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "las últimas notas")
        result = proc._match_obsidian_intent(normalized=norm, original_text="las últimas notas")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.list_last_n")
        self.assertEqual(result["params"]["n"], 5)

    def test_search_text_intent(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "busca verity")
        result = proc._match_obsidian_intent(normalized=norm, original_text="busca verity")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.search_text")
        self.assertEqual(result["params"]["query"], "verity")

    def test_search_text_buscar(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "buscar costes")
        result = proc._match_obsidian_intent(normalized=norm, original_text="buscar costes")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.search_text")

    def test_search_too_short_not_matched(self):
        """Single char query not matched (len < 2)."""
        proc = self._make_processor()
        norm = self._normalize(proc, "busca x")
        result = proc._match_obsidian_intent(normalized=norm, original_text="busca x")
        self.assertIsNone(result)

    def test_busca_nota_is_status_not_search(self):
        """'busca nota X' should resolve to show_note_status, not search_text."""
        proc = self._make_processor()
        norm = self._normalize(proc, "busca nota tg-001")
        result = proc._match_obsidian_intent(normalized=norm, original_text="busca nota tg-001")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.show_note_status")

    def test_summary_today_intent(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "resúmeme lo guardado hoy")
        result = proc._match_obsidian_intent(normalized=norm, original_text="resúmeme lo guardado hoy")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.summary_today")

    def test_notas_de_hoy(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "notas de hoy")
        result = proc._match_obsidian_intent(normalized=norm, original_text="notas de hoy")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "obsidian.summary_today")

    def test_unrelated_phrase_no_match(self):
        proc = self._make_processor()
        norm = self._normalize(proc, "hola mundo")
        result = proc._match_obsidian_intent(normalized=norm, original_text="hola mundo")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# TestPhase5TelegramHandlers
# ---------------------------------------------------------------------------

class TestPhase5TelegramHandlers(unittest.TestCase):
    """Test Phase 5 handler methods: vault not configured, no permission, happy path."""

    def _make_processor(self, vault_root: str = "", can_read: bool = True):
        from telegram_bot import TelegramCommandProcessor
        proc = TelegramCommandProcessor.__new__(TelegramCommandProcessor)
        mock_policy = MagicMock()
        mock_policy.vault_inbox.vault_root = vault_root
        proc.policy = mock_policy
        proc._can_operator = MagicMock(return_value=can_read)
        return proc

    def test_list_last_n_vault_not_configured(self):
        proc = self._make_processor(vault_root="")
        result = proc._vault_list_last_n(operator_id="op", n=5, chat_id="c", user_id="u")
        self.assertIn("vault_root", result)

    def test_list_last_n_no_permission(self):
        proc = self._make_processor(vault_root="/tmp", can_read=False)
        result = proc._vault_list_last_n(operator_id="op", n=5, chat_id="c", user_id="u")
        self.assertIn("autorizado", result.lower())

    def test_list_last_n_empty_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._make_processor(vault_root=tmp)
            result = proc._vault_list_last_n(operator_id="op", n=5, chat_id="c", user_id="u")
            self.assertIn("No hay notas", result)

    def test_list_last_n_with_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp) / "Agent" / "Inbox_Agent"
            inbox.mkdir(parents=True)
            (inbox / "20260414T100000Z_inbox_t1.md").write_text(
                '---\nrun_id: "r1"\ncapture_status: "pending_triage"\ncapture_title: "Title One"\n---\n# Title One\n\nBody.\n',
                encoding="utf-8",
            )
            proc = self._make_processor(vault_root=tmp)
            result = proc._vault_list_last_n(operator_id="op", n=3, chat_id="c", user_id="u")
            self.assertIn("20260414T100000Z_inbox_t1.md", result)

    def test_search_text_vault_not_configured(self):
        proc = self._make_processor(vault_root="")
        result = proc._vault_search_text(operator_id="op", query="verity", chat_id="c", user_id="u")
        self.assertIn("vault_root", result)

    def test_search_text_no_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_vault(tmp)
            proc = self._make_processor(vault_root=tmp)
            result = proc._vault_search_text(operator_id="op", query="zzznomatch", chat_id="c", user_id="u")
            self.assertIn("zzznomatch", result)

    def test_search_text_finds_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, _ = _make_vault(tmp)
            _note(inbox, "20260414T100000Z_inbox_s.md", title="Verity analysis", body="content")
            proc = self._make_processor(vault_root=tmp)
            result = proc._vault_search_text(operator_id="op", query="verity", chat_id="c", user_id="u")
            self.assertIn("Verity", result)

    def test_summary_today_vault_not_configured(self):
        proc = self._make_processor(vault_root="")
        result = proc._vault_summary_today(operator_id="op", chat_id="c", user_id="u")
        self.assertIn("vault_root", result)

    def test_summary_today_no_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_vault(tmp)
            proc = self._make_processor(vault_root=tmp)
            result = proc._vault_summary_today(operator_id="op", chat_id="c", user_id="u")
            self.assertIn("No hay", result)

    def test_extract_number_from_text(self):
        from telegram_bot import TelegramCommandProcessor
        self.assertEqual(TelegramCommandProcessor._extract_number_from_text("ultimas 7 notas", default=5, max_val=10), 7)
        self.assertEqual(TelegramCommandProcessor._extract_number_from_text("ultimas notas", default=5, max_val=10), 5)
        self.assertEqual(TelegramCommandProcessor._extract_number_from_text("ultimas 99 notas", default=5, max_val=10), 10)
        self.assertEqual(TelegramCommandProcessor._extract_number_from_text("ultimas 0 notas", default=5, max_val=10), 1)


if __name__ == "__main__":
    unittest.main()
