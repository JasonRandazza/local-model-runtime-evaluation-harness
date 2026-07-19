from __future__ import annotations

import threading

from .stage_two import ModelDescriptor, StageTwoError
from .stage_two_host import StageTwoReadOnlyTransport
from .transport import LoopbackTransport, TransportError, TransportResult


class StageTwoInferenceTransport:
    def __init__(self, allowed_base_urls: set[str], timeout_seconds: int) -> None:
        if timeout_seconds != 120:
            raise StageTwoError("transport_policy_failed", "Stage 2B timeout must be 120 seconds")
        self._read = StageTwoReadOnlyTransport(allowed_base_urls, timeout_seconds)
        self._chat = LoopbackTransport(allowed_base_urls, timeout_seconds)

    @staticmethod
    def _raise_sanitized_transport_error() -> None:
        raise StageTwoError("transport_failed", "Stage 2B inference transport failed") from None

    def health(self, base_url: str) -> dict[str, object]:
        try:
            result = self._read.health(base_url)
        except (StageTwoError, TransportError):
            pass
        else:
            return result
        self._raise_sanitized_transport_error()

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        try:
            result = self._read.list_models(base_url)
        except (StageTwoError, TransportError):
            pass
        else:
            return result
        self._raise_sanitized_transport_error()

    def chat(
        self,
        base_url: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        cancel: threading.Event,
    ) -> TransportResult:
        try:
            result = self._chat.chat(
                base_url, model_id, prompt, max_tokens, None, cancel,
            )
        except TransportError:
            pass
        else:
            return result
        self._raise_sanitized_transport_error()
