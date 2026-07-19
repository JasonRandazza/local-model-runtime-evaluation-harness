from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from local_model_runtime_evaluation.credentials import Credential
from local_model_runtime_evaluation.transport import LoopbackTransport, TransportError


class Handler(BaseHTTPRequestHandler):
    authorization = ""
    include_reasoning_details = True
    reasoning_tokens = 2

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({"loaded": [], "current_model": None, "resident_models": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "VibeThinker-3B-MLX-oQ4"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self) -> None:
        Handler.authorization = self.headers.get("Authorization", "")
        length = int(self.headers.get("Content-Length", "0"))
        json.loads(self.rfile.read(length))
        usage = {"completion_tokens": 4}
        if Handler.include_reasoning_details:
            usage["completion_tokens_details"] = {
                "reasoning_tokens": Handler.reasoning_tokens,
            }
        chunks = [
            {"choices": [{"delta": {"content": "hello"}, "finish_reason": None}]},
            {
                "choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}],
                "usage": usage,
            },
        ]
        body = "".join(f"data: {json.dumps(item)}\n\n" for item in chunks) + "data: [DONE]\n\n"
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class TransportTest(unittest.TestCase):
    def setUp(self) -> None:
        Handler.include_reasoning_details = True
        Handler.reasoning_tokens = 2
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_streams_result_and_lists_models_without_exposing_credential(self) -> None:
        credential = Credential("stage1-test-key")
        transport = LoopbackTransport({self.base_url})
        self.assertEqual(transport.list_models(self.base_url, credential), ("VibeThinker-3B-MLX-oQ4",))
        result = transport.chat(self.base_url, "VibeThinker-3B-MLX-oQ4", "hello", 16, credential)
        self.assertEqual(result.content, "hello world")
        self.assertEqual(result.completion_tokens, 4)
        self.assertEqual(result.reasoning_tokens, 2)
        self.assertEqual(result.visible_output_tokens, 2)
        self.assertEqual(result.token_accounting_status, "EXACT_VISIBLE")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.content_event_count, 2)
        self.assertGreaterEqual(result.last_content_seconds, result.ttft_seconds)
        self.assertGreaterEqual(result.total_seconds, result.ttft_seconds)
        self.assertEqual(Handler.authorization, "Bearer stage1-test-key")
        self.assertNotIn("stage1-test-key", repr(result))

    def test_missing_reasoning_details_marks_visible_tokens_incomparable(self) -> None:
        Handler.include_reasoning_details = False
        result = LoopbackTransport({self.base_url}).chat(
            self.base_url, "VibeThinker-3B-MLX-oQ4", "hello", 16, None
        )
        self.assertIsNone(result.reasoning_tokens)
        self.assertIsNone(result.visible_output_tokens)
        self.assertEqual(result.token_accounting_status, "INCOMPARABLE_TOKEN_ACCOUNTING")

    def test_rejects_reasoning_tokens_that_exceed_completion_total(self) -> None:
        Handler.reasoning_tokens = 5
        with self.assertRaises(TransportError):
            LoopbackTransport({self.base_url}).chat(
                self.base_url, "VibeThinker-3B-MLX-oQ4", "hello", 16, None
            )

    def test_routed_request_can_omit_direct_omlx_credential(self) -> None:
        transport = LoopbackTransport({self.base_url})
        self.assertEqual(transport.list_models(self.base_url, None), ("VibeThinker-3B-MLX-oQ4",))
        transport.chat(self.base_url, "VibeThinker-3B-MLX-oQ4", "hello", 16, None)
        self.assertEqual(Handler.authorization, "")
        self.assertEqual(transport.health(self.base_url)["loaded"], [])

    def test_rejects_unapproved_or_remote_endpoint(self) -> None:
        transport = LoopbackTransport({self.base_url})
        with self.assertRaises(TransportError):
            transport.list_models("http://example.com:8100/v1", Credential("key"))
        with self.assertRaises(TransportError):
            transport.list_models(f"http://127.0.0.1:{self.server.server_port}/other", Credential("key"))


if __name__ == "__main__":
    unittest.main()
