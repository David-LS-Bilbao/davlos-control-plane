from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "scripts" / "helpers"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import openclaw_vault_inbox_writer as inbox_writer  # noqa: E402


class InboxWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault_root = self.root / "vault-main"
        self.inbox_dir = self.vault_root / "Agent" / "Inbox_Agent"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.audit_root = self.root / "audit"
        self.input_dir = self.root / inbox_writer.CANONICAL_INPUT_DIR_NAME
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.input_file = self.input_dir / inbox_writer.CANONICAL_INPUT_NAME
        self.fixed_now = datetime(2026, 4, 9, 8, 30, tzinfo=timezone.utc)
        self._previous_utc_now = inbox_writer.utc_now
        inbox_writer.utc_now = lambda: self.fixed_now

    def tearDown(self) -> None:
        inbox_writer.utc_now = self._previous_utc_now
        self.tempdir.cleanup()

    def _write_request(
        self,
        *,
        operation: str = "inbox.write",
        schema_version: int = 1,
        run_id: str = "quick-capture-20260409T083000Z",
        capture_title: str = "Idea rapida de validacion",
        body: str = "Linea 1 de captura.\n\nLinea 2 de contexto.",
        source_refs: str = '["manual-test"]',
    ) -> None:
        self.input_file.write_text(
            "\n".join(
                [
                    "---",
                    f"operation: {operation}",
                    f"schema_version: {schema_version}",
                    f'run_id: "{run_id}"',
                    f'capture_title: "{capture_title}"',
                    f"source_refs: {source_refs}",
                    "---",
                    "",
                    body,
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def _args(self) -> Namespace:
        return Namespace(
            command="inbox.write",
            vault_root=str(self.vault_root),
            audit_root=str(self.audit_root),
            input_request_file=str(self.input_file),
        )

    def test_inbox_write_creates_note_and_audit(self) -> None:
        self._write_request()

        output = io.StringIO()
        with redirect_stdout(output):
            rc = inbox_writer.perform_inbox_write(self._args())

        self.assertEqual(rc, 0)
        note_path = (
            self.inbox_dir / "20260409T083000Z_inbox_quick-capture-20260409T083000Z.md"
        )
        self.assertTrue(note_path.is_file())
        rendered = note_path.read_text(encoding="utf-8")
        self.assertIn("agent_zone: Inbox_Agent", rendered)
        self.assertIn('capture_status: "pending_triage"', rendered)
        self.assertIn("# Idea rapida de validacion", rendered)

        audit_log = self.audit_root / inbox_writer.AUDIT_LOG_NAME
        self.assertTrue(audit_log.is_file())
        record = json.loads(audit_log.read_text(encoding="utf-8").strip())
        self.assertEqual(record["operation"], "inbox.write")
        self.assertEqual(record["run_id"], "quick-capture-20260409T083000Z")
        self.assertEqual(record["note_path"], str(note_path))

    def test_inbox_write_is_create_only(self) -> None:
        self._write_request(run_id="same-run-id")
        with redirect_stdout(io.StringIO()):
            inbox_writer.perform_inbox_write(self._args())

        with self.assertRaisesRegex(inbox_writer.WriterError, "already exists"):
            inbox_writer.perform_inbox_write(self._args())

    def test_inbox_write_rejects_symlinked_output_dir(self) -> None:
        self.inbox_dir.rmdir()
        redirected = self.root / "redirected-inbox"
        redirected.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.symlink_to(redirected, target_is_directory=True)
        self._write_request()

        with self.assertRaisesRegex(inbox_writer.WriterError, "symlink component"):
            inbox_writer.perform_inbox_write(self._args())

    def test_inbox_write_rejects_invalid_contract(self) -> None:
        self._write_request(operation="draft.write")

        with self.assertRaisesRegex(inbox_writer.WriterError, "operation must be inbox.write"):
            inbox_writer.perform_inbox_write(self._args())


if __name__ == "__main__":
    unittest.main()
