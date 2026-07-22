from __future__ import annotations

import unittest
from dataclasses import dataclass

from local_model_runtime_evaluation.credentials import Credential
from local_model_runtime_evaluation.matrix_servers import MATRIX_OMLX_API_KEY
from local_model_runtime_evaluation.omlx_thinking_pin import OmlxThinkingPin, default_pin_path
from local_model_runtime_evaluation.omlx_thinking_transport import (
    OmlxThinkingTransport,
    authorization_headers,
    build_chat_transport,
)
from local_model_runtime_evaluation.transport import TransportError, TransportResult


@dataclass
class FakeLoopback:
    list_models_calls: list[tuple[str, object | None]]
    chat_calls: list[tuple[str, str, str, int, object | None]]

    def __init__(self) -> None:
        self.list_models_calls = []
        self.chat_calls = []

    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
        self.list_models_calls.append((base_url, credential))
        return ("Qwen3.6-35B-A3B-OptiQ-4bit",)

    def chat(
        self,
        base_url: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        credential: object | None,
        cancel: object | None = None,
    ) -> TransportResult:
        self.chat_calls.append((base_url, model_id, prompt, max_tokens, credential))
        return TransportResult(
            content="visible answer",
            content_sha256="abc",
            ttft_seconds=0.1,
            total_seconds=0.2,
            completion_tokens=8,
            finish_reason="stop",
            http_status=200,
            stream_valid=True,
            content_event_count=1,
            last_content_seconds=0.15,
            reasoning_tokens=3,
            visible_output_tokens=5,
            token_accounting_status="EXACT_VISIBLE",
        )


class OmlxThinkingTransportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pin = OmlxThinkingPin.load(default_pin_path())
        self.loopback = FakeLoopback()

    def test_authorization_headers_default_matrix_local_key(self) -> None:
        headers = authorization_headers()
        self.assertEqual(headers, {"Authorization": f"Bearer {MATRIX_OMLX_API_KEY}"})

    def test_authorization_headers_use_injectable_credential(self) -> None:
        credential = Credential("custom-test-key")
        headers = authorization_headers(credential)
        self.assertEqual(headers, {"Authorization": "Bearer custom-test-key"})
        self.assertNotIn("custom-test-key", repr(credential))

    def test_list_models_delegates_with_credential(self) -> None:
        credential = Credential(MATRIX_OMLX_API_KEY)
        transport = OmlxThinkingTransport(
            self.pin.base_url,
            self.pin.model_id,
            credential=credential,
            loopback=self.loopback,
        )

        models = transport.list_models()

        self.assertEqual(models, ("Qwen3.6-35B-A3B-OptiQ-4bit",))
        self.assertEqual(len(self.loopback.list_models_calls), 1)
        base_url, seen_credential = self.loopback.list_models_calls[0]
        self.assertEqual(base_url, self.pin.base_url)
        self.assertIs(seen_credential, credential)

    def test_chat_delegates_with_model_id_and_credential(self) -> None:
        credential = Credential(MATRIX_OMLX_API_KEY)
        transport = OmlxThinkingTransport(
            self.pin.base_url,
            self.pin.model_id,
            credential=credential,
            loopback=self.loopback,
        )

        result = transport.chat("hello", 512)

        self.assertEqual(result.visible_text, "visible answer")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.reasoning_tokens, 3)
        self.assertEqual(result.visible_output_tokens, 5)
        self.assertEqual(result.token_accounting_status, "EXACT_VISIBLE")
        self.assertEqual(result.streaming_semantics, "incremental")
        self.assertEqual(result.content_span_seconds, 0.15)
        self.assertEqual(len(self.loopback.chat_calls), 1)
        base_url, model_id, prompt, max_tokens, seen_credential = self.loopback.chat_calls[0]
        self.assertEqual(base_url, self.pin.base_url)
        self.assertEqual(model_id, self.pin.model_id)
        self.assertEqual(prompt, "hello")
        self.assertEqual(max_tokens, 512)
        self.assertIs(seen_credential, credential)

    def test_for_pin_uses_matrix_local_credential(self) -> None:
        transport = OmlxThinkingTransport.for_pin(self.pin, loopback=self.loopback)
        transport.list_models()
        _, credential = self.loopback.list_models_calls[0]
        self.assertIsInstance(credential, Credential)
        self.assertEqual(credential.api_key(), MATRIX_OMLX_API_KEY)

    def test_repr_never_includes_api_key(self) -> None:
        transport = OmlxThinkingTransport.for_pin(self.pin, loopback=self.loopback)
        rendered = repr(transport)
        self.assertNotIn(MATRIX_OMLX_API_KEY, rendered)
        self.assertIn("REDACTED", rendered)

    def test_build_chat_transport_rejects_foreign_base_url(self) -> None:
        chat = build_chat_transport(self.pin, loopback=self.loopback)
        with self.assertRaises(TransportError):
            chat("http://127.0.0.1:9999/v1", "prompt", 512)

    def test_build_chat_transport_calls_loopback_on_approved_url(self) -> None:
        chat = build_chat_transport(self.pin, loopback=self.loopback)
        result = chat(self.pin.base_url, "prompt", 768)
        self.assertEqual(result.visible_text, "visible answer")
        self.assertEqual(self.loopback.chat_calls[0][2], "prompt")
        self.assertEqual(self.loopback.chat_calls[0][3], 768)


if __name__ == "__main__":
    unittest.main()
