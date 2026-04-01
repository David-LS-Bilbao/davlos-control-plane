from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from broker import RestrictedOperatorBroker
from models import BrokerRequest


class RestrictedOperatorHandler(BaseHTTPRequestHandler):
    broker: RestrictedOperatorBroker
    server_version = "DavlosRestrictedOperator/0.1"

    def do_GET(self) -> None:
        if self.path != "/healthz":
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        self._json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "restricted_operator",
                "api": "mvp_v1",
            },
        )

    def do_POST(self) -> None:
        if self.path != "/v1/actions/execute":
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
            return
        request = BrokerRequest(
            action_id=str(payload.get("action_id", "")),
            params=payload.get("params") or {},
            actor=str(payload.get("actor", "openclaw")),
        )
        result = self.broker.execute(request)
        status = HTTPStatus.OK if result.ok else HTTPStatus.BAD_REQUEST
        if result.code in {"unknown_action", "forbidden"}:
            status = HTTPStatus.FORBIDDEN
        elif result.code == "not_found":
            status = HTTPStatus.NOT_FOUND
        self._json(status, result.to_dict())

    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DAVLOS restricted operator broker MVP")
    parser.add_argument(
        "--policy",
        required=True,
        help="Path to restricted operator policy json",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    broker = RestrictedOperatorBroker(args.policy)
    RestrictedOperatorHandler.broker = broker
    server = ThreadingHTTPServer(
        (broker.policy.broker.bind_host, broker.policy.broker.bind_port),
        RestrictedOperatorHandler,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
