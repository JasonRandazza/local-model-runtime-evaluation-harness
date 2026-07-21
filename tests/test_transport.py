from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from local_model_runtime_evaluation.credentials import Credential
from local_model_runtime_evaluation.transport import LoopbackTransport, TransportError


class Handler(BaseHTTPRequestHandler):
    authorization = ""
    include_reasoning_details = True
    reasoning_tokens = 2
    stream_stall_seconds = 0.0
    first_event_sent = threading.Event()
    stream_release = threading.Event()

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
        if Handler.stream_stall_seconds:
            first_event = f"data: {json.dumps(chunks[0])}\n\n".encode()
            remainder = (
                f"data: {json.dumps(chunks[1])}\n\n"
                "data: [DONE]\n\n"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            try:
                self.wfile.write(first_event)
                self.wfile.flush()
                Handler.first_event_sent.set()
                Handler.stream_release.wait(Handler.stream_stall_seconds)
                self.wfile.write(remainder)
            except BrokenPipeError:
                return
            return
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
        Handler.stream_stall_seconds = 0.0
        Handler.first_event_sent = threading.Event()
        Handler.stream_release = threading.Event()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def tearDown(self) -> None:
        Handler.stream_release.set()
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

    def test_chat_enforces_monotonic_wall_clock_deadline_on_trickle_stream(self) -> None:
        Handler.stream_stall_seconds = 5.0
        transport = LoopbackTransport({self.base_url}, timeout_seconds=2)
        started = time.monotonic()

        with self.assertRaises(TransportError) as ctx:
            transport.chat(self.base_url, "model", "secret-prompt", 16, None)

        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 4.0)
        self.assertIn("timed out", str(ctx.exception).lower())
        self.assertNotIn("secret-prompt", str(ctx.exception))

    def test_chat_observes_cancellation_during_blocked_stream_read(self) -> None:
        Handler.stream_stall_seconds = 10.0
        cancel = threading.Event()

        def cancel_after_first_event() -> None:
            Handler.first_event_sent.wait()
            time.sleep(0.2)
            cancel.set()

        threading.Thread(target=cancel_after_first_event, daemon=True).start()
        transport = LoopbackTransport({self.base_url}, timeout_seconds=120)
        started = time.monotonic()

        with self.assertRaises(TransportError) as ctx:
            transport.chat(self.base_url, "model", "secret-prompt", 16, None, cancel=cancel)

        self.assertLess(time.monotonic() - started, 3.0)
        self.assertIn("cancelled", str(ctx.exception).lower())
        self.assertNotIn("secret-prompt", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
