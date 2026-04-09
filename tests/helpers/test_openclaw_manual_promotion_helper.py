from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "scripts" / "helpers"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import openclaw_manual_promotion_helper as helper  # noqa: E402


class ManualPromotionHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "openclaw-vault-inbox-writer").mkdir(parents=True, exist_ok=True)
        (self.root / "openclaw-vault-report-writer").mkdir(parents=True, exist_ok=True)
        (self.root / "vault-main" / "Agent" / "Inbox_Agent").mkdir(parents=True, exist_ok=True)
        (self.root / "vault-main" / "Agent" / "Reports_Agent").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_prepare_and_validate_inbox_input(self) -> None:
        output_file = self.root / "openclaw-vault-inbox-writer" / "INBOX_INPUT.md"
        prepare_args = Namespace(
            command="prepare",
            domain="inbox",
            output_file=str(output_file),
            run_id="manual-flow-inbox",
            title="Captura de validacion",
            body="Linea 1.\n\nLinea 2.",
            source_ref=["manual-flow"],
            proposed_target_path="",
            overwrite_existing=False,
        )

        output = io.StringIO()
        with redirect_stdout(output):
            rc = helper.prepare_input(prepare_args)
        self.assertEqual(rc, 0)
        created = json.loads(output.getvalue().strip())
        self.assertEqual(created["operation"], "inbox.write")
        self.assertTrue(output_file.is_file())

        validate_args = Namespace(
            command="validate",
            domain="inbox",
            input_file=str(output_file),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            rc = helper.validate_input(validate_args)
        self.assertEqual(rc, 0)
        validated = json.loads(output.getvalue().strip())
        self.assertEqual(validated["domain"], "inbox")
        self.assertEqual(validated["run_id"], "manual-flow-inbox")

    def test_prepare_draft_rejects_wrong_domain_path(self) -> None:
        wrong_output = self.root / "vault-main" / "Agent" / "Reports_Agent" / "STAGED_INPUT.md"
        args = Namespace(
            command="prepare",
            domain="draft",
            output_file=str(wrong_output),
            run_id="manual-flow-draft",
            title="Draft tecnico",
            body="Cuerpo tecnico.",
            source_ref=["Agent/Inbox_Agent/example.md"],
            proposed_target_path="",
            overwrite_existing=False,
        )

        with self.assertRaisesRegex(helper.HelperError, "must end with Agent/Inbox_Agent/STAGED_INPUT.md"):
            helper.prepare_input(args)

    def test_validate_report_rejects_invalid_contract(self) -> None:
        input_file = self.root / "openclaw-vault-report-writer" / "REPORT_INPUT.md"
        input_file.write_text(
            "\n".join(
                [
                    "---",
                    "operation: draft.write",
                    "schema_version: 1",
                    'run_id: "manual-flow-report"',
                    'report_title: "Informe corto"',
                    "---",
                    "",
                    "Texto.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        args = Namespace(
            command="validate",
            domain="report",
            input_file=str(input_file),
        )
        with self.assertRaisesRegex(helper.HelperError, "operation must be report.write"):
            helper.validate_input(args)

    def test_prepare_report_is_create_only_by_default(self) -> None:
        output_file = self.root / "openclaw-vault-report-writer" / "REPORT_INPUT.md"
        output_file.write_text("placeholder", encoding="utf-8")
        args = Namespace(
            command="prepare",
            domain="report",
            output_file=str(output_file),
            run_id="manual-flow-report",
            title="Informe de validacion",
            body="Texto tecnico.",
            source_ref=["Agent/Drafts_Agent/example.md"],
            proposed_target_path="",
            overwrite_existing=False,
        )

        with self.assertRaisesRegex(helper.HelperError, "output-file already exists"):
            helper.prepare_input(args)


if __name__ == "__main__":
    unittest.main()
