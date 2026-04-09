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

import openclaw_vault_report_writer as report_writer  # noqa: E402


class ReportWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault_root = self.root / "vault-main"
        self.reports_dir = self.vault_root / "Agent" / "Reports_Agent"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.audit_root = self.root / "audit"
        self.input_dir = self.root / report_writer.CANONICAL_INPUT_DIR_NAME
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.input_file = self.input_dir / report_writer.CANONICAL_INPUT_NAME
        self.fixed_now = datetime(2026, 4, 9, 9, 0, tzinfo=timezone.utc)
        self._previous_utc_now = report_writer.utc_now
        report_writer.utc_now = lambda: self.fixed_now

    def tearDown(self) -> None:
        report_writer.utc_now = self._previous_utc_now
        self.tempdir.cleanup()

    def _write_request(
        self,
        *,
        operation: str = "report.write",
        schema_version: int = 1,
        run_id: str = "short-report-20260409T090000Z",
        report_title: str = "Informe corto de validacion",
        body: str = "Resumen tecnico breve.\n\nHallazgo principal controlado.",
        source_refs: str = '["manual-test"]',
    ) -> None:
        self.input_file.write_text(
            "\n".join(
                [
                    "---",
                    f"operation: {operation}",
                    f"schema_version: {schema_version}",
                    f'run_id: "{run_id}"',
                    f'report_title: "{report_title}"',
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
            command="report.write",
            vault_root=str(self.vault_root),
            audit_root=str(self.audit_root),
            input_request_file=str(self.input_file),
        )

    def test_report_write_creates_note_and_audit(self) -> None:
        self._write_request()

        output = io.StringIO()
        with redirect_stdout(output):
            rc = report_writer.perform_report_write(self._args())

        self.assertEqual(rc, 0)
        note_path = (
            self.reports_dir / "20260409T090000Z_report_short-report-20260409T090000Z.md"
        )
        self.assertTrue(note_path.is_file())
        rendered = note_path.read_text(encoding="utf-8")
        self.assertIn("agent_zone: Reports_Agent", rendered)
        self.assertIn('report_status: "prepared"', rendered)
        self.assertIn("# Informe corto de validacion", rendered)

        audit_log = self.audit_root / report_writer.AUDIT_LOG_NAME
        self.assertTrue(audit_log.is_file())
        record = json.loads(audit_log.read_text(encoding="utf-8").strip())
        self.assertEqual(record["operation"], "report.write")
        self.assertEqual(record["run_id"], "short-report-20260409T090000Z")
        self.assertEqual(record["note_path"], str(note_path))

    def test_report_write_is_create_only(self) -> None:
        self._write_request(run_id="same-report-run")
        with redirect_stdout(io.StringIO()):
            report_writer.perform_report_write(self._args())

        with self.assertRaisesRegex(report_writer.WriterError, "already exists"):
            report_writer.perform_report_write(self._args())

    def test_report_write_rejects_symlinked_output_dir(self) -> None:
        self.reports_dir.rmdir()
        redirected = self.root / "redirected-reports"
        redirected.mkdir(parents=True, exist_ok=True)
        self.reports_dir.symlink_to(redirected, target_is_directory=True)
        self._write_request()

        with self.assertRaisesRegex(report_writer.WriterError, "symlink component"):
            report_writer.perform_report_write(self._args())

    def test_report_write_rejects_invalid_contract(self) -> None:
        self._write_request(operation="draft.write")

        with self.assertRaisesRegex(report_writer.WriterError, "operation must be report.write"):
            report_writer.perform_report_write(self._args())


if __name__ == "__main__":
    unittest.main()
