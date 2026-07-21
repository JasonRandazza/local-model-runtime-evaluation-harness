from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from local_model_runtime_evaluation.credentials import Credential
from local_model_runtime_evaluation.transport import LoopbackTransport, TransportError


class Handler(BaseHTTPRequestHandler):
    authorization = ""
    include_reasoning_details = True
    reasoning_tokens = 2
    stream_stall_seconds = 0.0
    stream_fragmented = False
    stream_trickle_interval = 0.0
    response_header_trickle_interval = 0.0
    error_body_trickle_interval = 0.0
    pre_first_event_delay_seconds = 0.0
    stream_body_override: bytes | None = None
    first_event_sent = threading.Event()
    stream_release = threading.Event()
    response_release = threading.Event()

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
        if Handler.response_header_trickle_interval:
            raw_headers = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/event-stream\r\n"
                b"Content-Length: 14\r\n"
                b"\r\n"
            )
            try:
                for byte in raw_headers:
                    if Handler.response_release.wait(Handler.response_header_trickle_interval):
                        return
                    self.wfile.write(bytes((byte,)))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
            except BrokenPipeError:
                return
            return
        if Handler.error_body_trickle_interval:
            body = b'{"error":"trickled response body past deadline"}'
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                for byte in body:
                    if Handler.response_release.wait(Handler.error_body_trickle_interval):
                        return
                    self.wfile.write(bytes((byte,)))
                    self.wfile.flush()
            except BrokenPipeError:
                return
            return
        if Handler.stream_body_override is not None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(Handler.stream_body_override)))
            self.end_headers()
            self.wfile.write(Handler.stream_body_override)
            return
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
            complete_first_event = f"data: {json.dumps(chunks[0])}\n\n".encode()
            if Handler.stream_fragmented:
                split_at = len(complete_first_event) // 2
                first_event = complete_first_event[:split_at]
                remaining_first_event = complete_first_event[split_at:]
            else:
                first_event = complete_first_event
                remaining_first_event = b""
            remainder = (
                remaining_first_event
                + f"data: {json.dumps(chunks[1])}\n\n".encode()
                + b"data: [DONE]\n\n"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            try:
                self.wfile.write(first_event)
                self.wfile.flush()
                Handler.first_event_sent.set()
                if Handler.stream_trickle_interval:
                    elapsed = 0.0
                    while elapsed < Handler.stream_stall_seconds:
                        Handler.stream_release.wait(Handler.stream_trickle_interval)
                        if Handler.stream_release.is_set():
                            return
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        elapsed += Handler.stream_trickle_interval
                else:
                    Handler.stream_release.wait(Handler.stream_stall_seconds)
                self.wfile.write(remainder)
            except BrokenPipeError:
                return
            return
        body = "".join(f"data: {json.dumps(item)}\n\n" for item in chunks) + "data: [DONE]\n\n"
        if Handler.pre_first_event_delay_seconds:
            # OptiQ-style: headers first, then prompt-processing keepalives that may
            # arrive more than one second after the stream opens.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            try:
                time.sleep(Handler.pre_first_event_delay_seconds)
                self.wfile.write(b": keepalive 1/1\n\n")
                self.wfile.flush()
                self.wfile.write(body.encode())
                self.wfile.flush()
            except BrokenPipeError:
                return
            return
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
        Handler.stream_fragmented = False
        Handler.stream_trickle_interval = 0.0
        Handler.response_header_trickle_interval = 0.0
        Handler.error_body_trickle_interval = 0.0
        Handler.pre_first_event_delay_seconds = 0.0
        Handler.stream_body_override = None
        Handler.first_event_sent = threading.Event()
        Handler.stream_release = threading.Event()
        Handler.response_release = threading.Event()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def tearDown(self) -> None:
        Handler.stream_release.set()
        Handler.response_release.set()
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
        Handler.stream_fragmented = True
        Handler.stream_trickle_interval = 0.1
        transport = LoopbackTransport({self.base_url}, timeout_seconds=2)
        started = time.monotonic()

        with self.assertRaises(TransportError) as ctx:
            transport.chat(self.base_url, "model", "secret-prompt", 16, None)

        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 4.0)
        self.assertIn("timed out", str(ctx.exception).lower())
        self.assertNotIn("secret-prompt", str(ctx.exception))

    def test_chat_enforces_deadline_while_receiving_trickled_response_headers(self) -> None:
        Handler.response_header_trickle_interval = 0.1
        transport = LoopbackTransport({self.base_url}, timeout_seconds=1)
        started = time.monotonic()

        with self.assertRaisesRegex(TransportError, "^request timed out$"):
            transport.chat(self.base_url, "model", "secret-prompt", 16, None)

        self.assertLess(time.monotonic() - started, 3.0)

    def test_chat_enforces_deadline_while_draining_trickled_error_body(self) -> None:
        Handler.error_body_trickle_interval = 0.1
        transport = LoopbackTransport({self.base_url}, timeout_seconds=1)
        started = time.monotonic()

        with self.assertRaisesRegex(TransportError, "^request timed out$"):
            transport.chat(self.base_url, "model", "secret-prompt", 16, None)

        self.assertLess(time.monotonic() - started, 3.0)

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

    def test_chat_consumes_sse_bytes_buffered_before_socket_readiness(self) -> None:
        buffered_stream = (
            b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}],'
            b'"usage":{"completion_tokens":1}}\n\n'
            b"data: [DONE]\n\n"
        )

        class FakeSocket:
            def settimeout(self, _timeout: float) -> None:
                return

        class FakeReader:
            raw = type("Raw", (), {"_sock": FakeSocket()})()

            def peek(self, _size: int) -> bytes:
                return buffered_stream

            def read1(self, _size: int) -> bytes:
                nonlocal buffered_stream
                chunk = buffered_stream
                buffered_stream = b""
                return chunk

        class FakeResponse:
            status = 200
            fp = FakeReader()

            @staticmethod
            def getheader(name: str, default: str = "") -> str:
                return "text/event-stream" if name == "Content-Type" else default

        class FakeConnection:
            sock = None

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                return

            def request(self, *_args: object, **_kwargs: object) -> None:
                return

            @staticmethod
            def getresponse() -> FakeResponse:
                return FakeResponse()

            def close(self) -> None:
                return

        with (
            patch("local_model_runtime_evaluation.transport.http.client.HTTPConnection", FakeConnection),
            patch("local_model_runtime_evaluation.transport.select.select", return_value=([], [], [])),
        ):
            result = LoopbackTransport({self.base_url}, timeout_seconds=1).chat(
                self.base_url, "model", "prompt", 16, None
            )

        self.assertEqual(result.content, "reply")

    def test_chat_rejects_eof_without_done(self) -> None:
        Handler.stream_body_override = (
            b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}]}\n\n'
        )

        with self.assertRaisesRegex(TransportError, "incomplete"):
            LoopbackTransport({self.base_url}).chat(self.base_url, "model", "prompt", 16, None)

    def test_chat_rejects_unexpected_non_data_line(self) -> None:
        Handler.stream_body_override = (
            b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":null}]}\n\n'
            b"event: message\n\n"
            b"data: [DONE]\n\n"
        )

        with self.assertRaisesRegex(TransportError, "framing"):
            LoopbackTransport({self.base_url}).chat(self.base_url, "model", "prompt", 16, None)

    def test_chat_allows_sse_comment_lines(self) -> None:
        Handler.stream_body_override = (
            b": keepalive\n\n"
            b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}]}\n\n'
            b"data: [DONE]\n\n"
        )

        result = LoopbackTransport({self.base_url}).chat(self.base_url, "model", "prompt", 16, None)

        self.assertEqual(result.content, "reply")

    def test_chat_survives_keepalive_gap_longer_than_one_second(self) -> None:
        # Regression for Stage 2B-1 cohorts 001-003: a 1s socket timeout during
        # peek permanently poisons http.client's stream reader on macOS/Python,
        # surfacing as stream_failed + OptiQ BrokenPipeError mid-keepalive.
        Handler.pre_first_event_delay_seconds = 1.2

        result = LoopbackTransport({self.base_url}, timeout_seconds=30).chat(
            self.base_url, "model", "prompt", 16, None
        )

        self.assertEqual(result.content, "hello world")

    def test_chat_rejects_leading_whitespace_sse_framing(self) -> None:
        for invalid_line in (
            b' data: {"choices":[{"delta":{"content":"ignored"},"finish_reason":null}]}\n\n',
            b" : keepalive\n\n",
        ):
            with self.subTest(invalid_line=invalid_line):
                Handler.stream_body_override = (
                    invalid_line
                    + b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}]}\n\n'
                    + b"data: [DONE]\n\n"
                )

                with self.assertRaisesRegex(TransportError, "framing"):
                    LoopbackTransport({self.base_url}).chat(
                        self.base_url, "model", "prompt", 16, None
                    )

    def test_chat_rejects_malformed_data_payload(self) -> None:
        Handler.stream_body_override = b"data: {not-json}\n\ndata: [DONE]\n\n"

        with self.assertRaises(TransportError):
            LoopbackTransport({self.base_url}).chat(self.base_url, "model", "prompt", 16, None)

    def test_chat_sanitizes_pre_stream_timeouts_and_cancellation(self) -> None:
        class FakeConnection:
            failure_site = "request"

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                return

            def request(self, *_args: object, **_kwargs: object) -> None:
                if self.failure_site == "request":
                    raise TimeoutError("prompt secret")

            def getresponse(self) -> object:
                if self.failure_site == "getresponse":
                    raise TimeoutError("prompt secret")
                raise AssertionError("a pre-stream timeout should be configured")

            def close(self) -> None:
                return

        with patch("local_model_runtime_evaluation.transport.http.client.HTTPConnection", FakeConnection):
            for failure_site in ("request", "getresponse"):
                with self.subTest(failure_site=failure_site):
                    FakeConnection.failure_site = failure_site
                    with self.assertRaisesRegex(TransportError, "^request timed out$"):
                        LoopbackTransport({self.base_url}).chat(
                            self.base_url, "model", "secret-prompt", 16, None
                        )

            cancel = threading.Event()
            cancel.set()
            FakeConnection.failure_site = "request"
            with self.assertRaisesRegex(TransportError, "^request cancelled$"):
                LoopbackTransport({self.base_url}).chat(
                    self.base_url, "model", "secret-prompt", 16, None, cancel=cancel
                )


if __name__ == "__main__":
    unittest.main()
