from __future__ import annotations

import json
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from local_model_runtime_evaluation.matrix_config import Cell, MatrixSuite
from local_model_runtime_evaluation.matrix_measure import measure_cell
from local_model_runtime_evaluation.transport import LoopbackTransport


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "suites/gemma-matrix-v1.json"
OSAURUS_BASE = "http://127.0.0.1:1337/v1"


class FakeProbe:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def free_memory_percent(self) -> int:
        return self.values.pop(0)


class ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    model_id = "gemma-4-12b-it-qat-jang_4m"
    posts = 0
    fail_posts: set[int] = set()
    bad_contract = False

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": Handler.model_id}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        Handler.posts += 1
        if Handler.posts in Handler.fail_posts:
            self.send_response(500)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        prompt = payload["messages"][0]["content"]
        if "Return exactly this JSON" in prompt:
            if Handler.bad_contract:
                content = '{"name":"wrong","arguments":{}}'
            else:
                content = '{"name":"status","arguments":{"run_id":"stage1-test","include_details":false}}'
        else:
            content = "First sentence. Second sentence."
        chunks = [
            {
                "choices": [{"delta": {"content": content}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 8},
            },
        ]
        body = "".join(f"data: {json.dumps(item)}\n\n" for item in chunks) + "data: [DONE]\n\n"
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _osaurus_cell(**overrides: object) -> Cell:
    data = dict(
        cell_id="jang_4m__osaurus",
        quant="jang_4m",
        server="osaurus",
        base_url=OSAURUS_BASE,
        model_id="gemma-4-12b-it-qat-jang_4m",
        artifact_path="/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
        start_command=("osaurus", "serve", "--port", "1337", "--yes"),
        stop_command=("osaurus", "stop"),
        health_path="/health",
        notes="",
    )
    data.update(overrides)
    return Cell(**data)  # type: ignore[arg-type]


class MatrixMeasureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", 1337))
            except OSError as error:
                raise unittest.SkipTest(f"port 1337 unavailable: {error}") from error

    def setUp(self) -> None:
        Handler.model_id = "gemma-4-12b-it-qat-jang_4m"
        Handler.posts = 0
        Handler.fail_posts = set()
        Handler.bad_contract = False
        self.server = ReuseHTTPServer(("127.0.0.1", 1337), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_screen_run_counts_twelve_posts(self) -> None:
        result = measure_cell(
            _osaurus_cell(),
            MatrixSuite.load(SUITE),
            "screen",
            LoopbackTransport({OSAURUS_BASE}),
            FakeProbe([80, 79]),
            threading.Event(),
        )
        self.assertEqual(Handler.posts, 12)
        self.assertEqual(result.status, "PASS")
        self.assertIsNone(result.na_reason)
        self.assertEqual(result.summary["measured_count"], 9)
        self.assertEqual(result.summary["contract_pass_count"], 9)
        self.assertEqual(result.memory_free_percent_before, 80)
        self.assertEqual(result.memory_free_percent_after, 79)

    def test_missing_model_returns_na_without_posts(self) -> None:
        Handler.model_id = "something-else"
        result = measure_cell(
            _osaurus_cell(),
            MatrixSuite.load(SUITE),
            "screen",
            LoopbackTransport({OSAURUS_BASE}),
            FakeProbe([80, 79]),
            threading.Event(),
        )
        self.assertEqual(Handler.posts, 0)
        self.assertEqual(result.status, "N/A")
        self.assertIn("exact model id", result.na_reason or "")
        self.assertEqual(result.summary["measured_count"], 0)

    def test_measured_transport_failure_marks_fail_but_finishes(self) -> None:
        Handler.fail_posts = {3, 7}
        result = measure_cell(
            _osaurus_cell(),
            MatrixSuite.load(SUITE),
            "screen",
            LoopbackTransport({OSAURUS_BASE}),
            None,
            threading.Event(),
        )
        self.assertEqual(Handler.posts, 12)
        self.assertEqual(result.status, "FAIL")
        measured = [item for item in result.observations if item.measured]
        self.assertEqual(len(measured), 9)
        self.assertEqual(sum(1 for item in measured if not item.success), 2)

    def test_measured_contract_failure_marks_fail(self) -> None:
        Handler.bad_contract = True
        result = measure_cell(
            _osaurus_cell(),
            MatrixSuite.load(SUITE),
            "screen",
            LoopbackTransport({OSAURUS_BASE}),
            None,
            threading.Event(),
        )
        self.assertEqual(result.status, "FAIL")
        measured = [item for item in result.observations if item.measured]
        self.assertEqual(sum(1 for item in measured if not item.response_contract_valid), 3)

    def test_finalist_run_counts_eighteen_posts(self) -> None:
        result = measure_cell(
            _osaurus_cell(),
            MatrixSuite.load(SUITE),
            "finalist",
            LoopbackTransport({OSAURUS_BASE}),
            None,
            threading.Event(),
        )
        self.assertEqual(Handler.posts, 18)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.summary["measured_count"], 15)


if __name__ == "__main__":
    unittest.main()
