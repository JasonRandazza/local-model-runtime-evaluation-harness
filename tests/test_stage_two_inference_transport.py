from __future__ import annotations

import inspect
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from local_model_runtime_evaluation.stage_two import ModelDescriptor, StageTwoError
from local_model_runtime_evaluation.stage_two_inference_transport import StageTwoInferenceTransport
from local_model_runtime_evaluation.transport import TransportError


class CaptureHandler(BaseHTTPRequestHandler):
    records: list[dict[str, object]] = []
    post_status = 200
    post_content_type = "text/event-stream"
    post_body = (
        'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}]}\n\n'
        "data: [DONE]\n\n"
    ).encode()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _record(self, body: bytes = b"") -> None:
        self.records.append({
            "method": self.command,
            "path": self.path,
            "body": json.loads(body) if body else None,
            "headers": dict(self.headers.items()),
        })

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._record()
        if self.path == "/health":
            self._respond(200, "application/json", b'{"status":"ok"}')
            return
        if self.path == "/v1/models":
            self._respond(
                200,
                "application/json",
                b'{"data":[{"id":"mlx-community/VibeThinker-3B-OptiQ-4bit"}]}',
            )
            return
        self._respond(404, "application/json", b'{"error":"unexpected path"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self._record(self.rfile.read(length))
        self._respond(self.post_status, self.post_content_type, self.post_body)


def raise_nested_stage_two_error(*_args: object) -> None:
    try:
        json.loads("{malformed-json")
    except json.JSONDecodeError as error:
        raise StageTwoError("transport_failed", "GET endpoint request failed") from error
    raise AssertionError("malformed JSON unexpectedly parsed")


class StageTwoInferenceTransportTest(unittest.TestCase):
    def setUp(self) -> None:
        CaptureHandler.records = []
        CaptureHandler.post_status = 200
        CaptureHandler.post_content_type = "text/event-stream"
        CaptureHandler.post_body = (
            'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}],'
            '"usage":{"completion_tokens":1}}\n\n'
            "data: [DONE]\n\n"
        ).encode()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.transport = StageTwoInferenceTransport({self.base_url}, 120)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_chat_has_no_credential_argument_and_sends_exact_credential_free_request(self) -> None:
        parameters = inspect.signature(StageTwoInferenceTransport.chat).parameters
        self.assertNotIn("credential", parameters)

        result = self.transport.chat(
            self.base_url,
            "mlx-community/VibeThinker-3B-OptiQ-4bit",
            "fixed prompt",
            128,
            threading.Event(),
        )

        self.assertEqual(result.content, "reply")
        request = CaptureHandler.records[-1]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["path"], "/v1/chat/completions")
        self.assertEqual(request["body"], {
            "model": "mlx-community/VibeThinker-3B-OptiQ-4bit",
            "messages": [{"role": "user", "content": "fixed prompt"}],
            "temperature": 0,
            "max_tokens": 128,
            "stream": True,
            "stream_options": {"include_usage": True},
        })
        self.assertNotIn("Authorization", request["headers"])

    def test_health_and_inventory_compose_existing_read_only_transport(self) -> None:
        self.assertEqual(self.transport.health(self.base_url), {"status": "ok"})
        self.assertEqual(
            self.transport.list_models(self.base_url),
            (ModelDescriptor("mlx-community/VibeThinker-3B-OptiQ-4bit"),),
        )
        self.assertEqual([item["method"] for item in CaptureHandler.records], ["GET", "GET"])
        self.assertEqual([item["path"] for item in CaptureHandler.records], ["/health", "/v1/models"])

    def test_init_rejects_any_timeout_other_than_120_seconds(self) -> None:
        with self.assertRaises(StageTwoError) as raised:
            StageTwoInferenceTransport({self.base_url}, 119)
        self.assertEqual(raised.exception.code, "transport_policy_failed")

    def test_rejects_remote_host_localhost_https_and_wrong_base_path(self) -> None:
        for base_url in (
            "http://example.com:8100/v1",
            f"http://localhost:{self.server.server_port}/v1",
            f"https://127.0.0.1:{self.server.server_port}/v1",
            f"http://127.0.0.1:{self.server.server_port}/other",
        ):
            with self.subTest(base_url=base_url), self.assertRaises(StageTwoError) as raised:
                self.transport.health(base_url)
            self.assertEqual(raised.exception.code, "transport_failed")
            self.assertEqual(str(raised.exception), "Stage 2B inference transport failed")

    def test_read_only_transport_rejects_wrong_get_path(self) -> None:
        with self.assertRaises(StageTwoError) as raised:
            self.transport._read._request(self.base_url, "/v1/chat/completions")
        self.assertEqual(raised.exception.code, "endpoint_forbidden")
        self.assertEqual(CaptureHandler.records, [])

    def test_rejects_non_sse_post_response(self) -> None:
        CaptureHandler.post_content_type = "application/json"
        CaptureHandler.post_body = b'{"error":"response body secret"}'
        with self.assertRaises(StageTwoError) as raised:
            self.transport.chat(self.base_url, "model-id", "prompt secret", 128, threading.Event())
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertNotIn("response body secret", str(raised.exception))
        self.assertNotIn("prompt secret", str(raised.exception))

    def test_rejects_http_error_without_exposing_response_body(self) -> None:
        CaptureHandler.post_status = 500
        CaptureHandler.post_body = b'{"error":"header secret and generated output"}'
        with self.assertRaises(StageTwoError) as raised:
            self.transport.chat(self.base_url, "model-id", "prompt secret", 128, threading.Event())
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertNotIn("header secret", str(raised.exception))
        self.assertNotIn("generated output", str(raised.exception))
        self.assertNotIn("prompt secret", str(raised.exception))

    def test_rejects_empty_stream(self) -> None:
        CaptureHandler.post_body = b"data: [DONE]\n\n"
        with self.assertRaises(StageTwoError) as raised:
            self.transport.chat(self.base_url, "model-id", "prompt", 128, threading.Event())
        self.assertEqual(raised.exception.code, "transport_failed")

    def test_rejects_malformed_sse(self) -> None:
        CaptureHandler.post_body = b"data: {not-json}\n\n"
        with self.assertRaises(StageTwoError) as raised:
            self.transport.chat(self.base_url, "model-id", "prompt secret", 128, threading.Event())
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertNotIn("prompt secret", str(raised.exception))

    def test_rejects_incomplete_sse_without_prompt_leakage(self) -> None:
        CaptureHandler.post_body = (
            b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}]}\n\n'
        )
        with self.assertRaises(StageTwoError) as raised:
            self.transport.chat(self.base_url, "model-id", "prompt secret", 128, threading.Event())
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertNotIn("prompt secret", str(raised.exception))

    def test_rejects_unsupported_sse_framing_without_prompt_leakage(self) -> None:
        CaptureHandler.post_body = (
            b"event: message\n\n"
            b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}]}\n\n'
            b"data: [DONE]\n\n"
        )
        with self.assertRaises(StageTwoError) as raised:
            self.transport.chat(self.base_url, "model-id", "prompt secret", 128, threading.Event())
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertNotIn("prompt secret", str(raised.exception))

    def test_rejects_leading_whitespace_sse_framing_without_prompt_leakage(self) -> None:
        for invalid_line in (
            b' data: {"choices":[{"delta":{"content":"ignored"},"finish_reason":null}]}\n\n',
            b" : keepalive\n\n",
        ):
            with self.subTest(invalid_line=invalid_line):
                CaptureHandler.post_body = (
                    invalid_line
                    + b'data: {"choices":[{"delta":{"content":"reply"},"finish_reason":"stop"}]}\n\n'
                    + b"data: [DONE]\n\n"
                )
                with self.assertRaises(StageTwoError) as raised:
                    self.transport.chat(
                        self.base_url, "model-id", "prompt secret", 128, threading.Event()
                    )
                self.assertEqual(raised.exception.code, "transport_failed")
                self.assertNotIn("prompt secret", str(raised.exception))

    def test_translates_cancellation_without_exposing_prompt(self) -> None:
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(StageTwoError) as raised:
            self.transport.chat(self.base_url, "model-id", "prompt secret", 128, cancel)
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertNotIn("prompt secret", str(raised.exception))

    def test_fake_connection_receives_120_second_timeout_and_timeout_is_sanitized(self) -> None:
        observed: dict[str, object] = {}

        class FakeConnection:
            def __init__(self, host: str, port: int, timeout: int) -> None:
                observed["host"] = host
                observed["port"] = port
                observed["timeout"] = timeout

            def request(self, method: str, path: str, **kwargs: object) -> None:
                observed["request"] = (method, path, kwargs)

            def getresponse(self) -> object:
                raise TimeoutError("prompt secret generated content")

            def close(self) -> None:
                observed["closed"] = True

        with patch("local_model_runtime_evaluation.transport.http.client.HTTPConnection", FakeConnection):
            with self.assertRaises(StageTwoError) as raised:
                self.transport.chat(self.base_url, "model-id", "prompt secret", 128, threading.Event())

        self.assertEqual(observed["timeout"], 120)
        self.assertTrue(observed["closed"])
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertNotIn("prompt secret", str(raised.exception))
        self.assertNotIn("generated content", str(raised.exception))

    def test_translates_transport_error_without_copying_sensitive_message(self) -> None:
        with patch.object(
            self.transport._chat,
            "chat",
            side_effect=TransportError("Authorization: bearer secret; output secret; prompt secret"),
        ):
            with self.assertRaises(StageTwoError) as raised:
                self.transport.chat(self.base_url, "model-id", "prompt secret", 128, threading.Event())
        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertEqual(str(raised.exception), "Stage 2B inference transport failed")

    def test_chat_translation_has_no_exception_cause_chain(self) -> None:
        with patch.object(
            self.transport._chat,
            "chat",
            side_effect=TransportError("transport detail secret"),
        ):
            with self.assertRaises(StageTwoError) as raised:
                self.transport.chat(self.base_url, "model-id", "prompt", 128, threading.Event())

        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertEqual(str(raised.exception), "Stage 2B inference transport failed")
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_health_translation_sanitizes_nested_json_cause(self) -> None:
        with patch.object(self.transport._read, "health", side_effect=raise_nested_stage_two_error):
            with self.assertRaises(StageTwoError) as raised:
                self.transport.health(self.base_url)

        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertEqual(str(raised.exception), "Stage 2B inference transport failed")
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_model_translation_sanitizes_nested_json_cause(self) -> None:
        with patch.object(self.transport._read, "list_models", side_effect=raise_nested_stage_two_error):
            with self.assertRaises(StageTwoError) as raised:
                self.transport.list_models(self.base_url)

        self.assertEqual(raised.exception.code, "transport_failed")
        self.assertEqual(str(raised.exception), "Stage 2B inference transport failed")
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)


if __name__ == "__main__":
    unittest.main()
