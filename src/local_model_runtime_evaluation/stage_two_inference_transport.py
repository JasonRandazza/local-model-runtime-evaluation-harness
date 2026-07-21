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
    def _raise_sanitized_transport_error(
        error: TransportError | None = None,
    ) -> None:
        reason = "transport_failed"
        http_status = None
        if error is not None:
            reason = error.reason or "transport_failed"
            http_status = error.http_status
        raise StageTwoError(
            "transport_failed",
            "Stage 2B inference transport failed",
            reason=reason,
            http_status=http_status,
        ) from None

    def health(self, base_url: str) -> dict[str, object]:
        captured: TransportError | None = None
        try:
            result = self._read.health(base_url)
        except TransportError as error:
            captured = error
        except StageTwoError:
            pass
        else:
            return result
        self._raise_sanitized_transport_error(captured)

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        captured: TransportError | None = None
        try:
            result = self._read.list_models(base_url)
        except TransportError as error:
            captured = error
        except StageTwoError:
            pass
        else:
            return result
        self._raise_sanitized_transport_error(captured)

    def chat(
        self,
        base_url: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        cancel: threading.Event,
    ) -> TransportResult:
        captured: TransportError | None = None
        try:
            result = self._chat.chat(
                base_url, model_id, prompt, max_tokens, None, cancel,
            )
        except TransportError as error:
            captured = error
        else:
            return result
        self._raise_sanitized_transport_error(captured)
