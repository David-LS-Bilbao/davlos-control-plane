from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "scripts" / "agents" / "openclaw" / "restricted_operator"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from broker import RestrictedOperatorBroker  # noqa: E402
from models import BrokerRequest  # noqa: E402


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"accepted":true}')

    def log_message(self, fmt: str, *args) -> None:
        return


class BrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.log_path = self.root / "logs" / "openclaw-current.log"
        self.audit_path = self.root / "audit" / "restricted_operator.jsonl"
        self.dropzone = self.root / "dropzone"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("line-1\nline-2\nline-3\n")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _OkHandler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

        self.policy_path = self.root / "policy.json"
        self.policy_path.write_text(
            json.dumps(
                {
                    "broker": {
                        "bind_host": "127.0.0.1",
                        "bind_port": 18890,
                        "audit_log_path": str(self.audit_path),
                        "dropzone_dir": str(self.dropzone),
                        "max_tail_lines": 20,
                        "max_write_bytes": 128,
                    },
                    "actions": {
                        "action.health.general.v1": {"enabled": True, "permission": "read", "description": ""},
                        "action.logs.read.v1": {"enabled": True, "permission": "read", "description": ""},
                        "action.webhook.trigger.v1": {"enabled": True, "permission": "trigger", "description": ""},
                        "action.openclaw.restart.v1": {"enabled": False, "permission": "control", "description": ""},
                        "action.dropzone.write.v1": {"enabled": True, "permission": "write", "description": ""}
                    },
                    "health_checks": {
                        "local_ok": {"url": f"{self.base_url}/healthz", "expect_status": 200}
                    },
                    "log_streams": {
                        "openclaw_runtime": {
                            "path": str(self.log_path),
                            "tail_lines_default": 2
                        }
                    },
                    "webhook_targets": {
                        "controlled": {
                            "url": f"{self.base_url}/hook",
                            "method": "POST",
                            "timeout_seconds": 5
                        }
                    }
                }
            )
        )
        self.broker = RestrictedOperatorBroker(str(self.policy_path))

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tempdir.cleanup()

    def test_health_action(self) -> None:
        result = self.broker.execute(BrokerRequest(action_id="action.health.general.v1"))
        self.assertTrue(result.ok)
        self.assertEqual(result.result["checks"]["local_ok"]["status"], 200)

    def test_logs_action(self) -> None:
        result = self.broker.execute(
            BrokerRequest(
                action_id="action.logs.read.v1",
                params={"stream_id": "openclaw_runtime", "tail_lines": 2},
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.result["lines"], ["line-2", "line-3"])

    def test_dropzone_write_rejects_traversal(self) -> None:
        result = self.broker.execute(
            BrokerRequest(
                action_id="action.dropzone.write.v1",
                params={"filename": "../bad.txt", "content": "hello"},
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "invalid_params")

    def test_webhook_action(self) -> None:
        result = self.broker.execute(
            BrokerRequest(
                action_id="action.webhook.trigger.v1",
                params={"target_id": "controlled", "event_type": "ping", "note": "test"},
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.result["status"], 200)

    def test_disabled_restart_action(self) -> None:
        result = self.broker.execute(BrokerRequest(action_id="action.openclaw.restart.v1"))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "forbidden")


if __name__ == "__main__":
    unittest.main()
