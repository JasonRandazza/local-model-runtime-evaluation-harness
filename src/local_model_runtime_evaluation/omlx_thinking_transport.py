from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .credentials import Credential
from .matrix_servers import MATRIX_OMLX_API_KEY
from .omlx_thinking_pin import OmlxThinkingPin
from .transport import LoopbackTransport, TransportError

ChatTransport = Callable[[str, str, int], "ThinkingChatResponse"]
ThinkingTransportFactory = Callable[[], "OmlxThinkingTransport"]


class LoopbackClient(Protocol):
    def list_models(self, base_url: str, credential: Credential | None) -> tuple[str, ...]: ...

    def chat(
        self,
        base_url: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        credential: Credential | None,
        cancel: object | None = None,
    ) -> object: ...


def matrix_local_credential() -> Credential:
    return Credential(MATRIX_OMLX_API_KEY)


def authorization_headers(credential: Credential | None = None) -> dict[str, str]:
    resolved = credential or matrix_local_credential()
    return {"Authorization": resolved.authorization_header()}


@dataclass(frozen=True)
class ThinkingChatResponse:
    visible_text: str
    finish_reason: str | None = None


@dataclass(repr=False)
class OmlxThinkingTransport:
    base_url: str
    model_id: str
    credential: Credential
    loopback: LoopbackClient

    def __repr__(self) -> str:
        return (
            "OmlxThinkingTransport("
            f"base_url={self.base_url!r}, model_id={self.model_id!r}, "
            f"credential={self.credential!r})"
        )

    @classmethod
    def for_pin(
        cls,
        pin: OmlxThinkingPin,
        *,
        credential: Credential | None = None,
        loopback: LoopbackClient | None = None,
        timeout_seconds: int = 120,
    ) -> OmlxThinkingTransport:
        if pin.api_key_source != "matrix_local":
            raise TransportError(
                "pin api_key_source is not supported",
                reason="unsupported_api_key_source",
            )
        resolved = credential or matrix_local_credential()
        client = loopback or LoopbackTransport({pin.base_url}, timeout_seconds=timeout_seconds)
        return cls(pin.base_url, pin.model_id, resolved, client)

    def list_models(self) -> tuple[str, ...]:
        return self.loopback.list_models(self.base_url, self.credential)

    def chat(self, prompt: str, max_tokens: int) -> ThinkingChatResponse:
        result = self.loopback.chat(
            self.base_url,
            self.model_id,
            prompt,
            max_tokens,
            self.credential,
        )
        return ThinkingChatResponse(
            visible_text=str(result.content),
            finish_reason=result.finish_reason,
        )


def build_chat_transport(
    pin: OmlxThinkingPin,
    *,
    credential: Credential | None = None,
    loopback: LoopbackClient | None = None,
    timeout_seconds: int = 120,
) -> ChatTransport:
    transport = OmlxThinkingTransport.for_pin(
        pin,
        credential=credential,
        loopback=loopback,
        timeout_seconds=timeout_seconds,
    )

    def chat(base_url: str, prompt: str, max_tokens: int) -> ThinkingChatResponse:
        if base_url != pin.base_url:
            raise TransportError("endpoint is not approved", reason="endpoint_forbidden")
        return transport.chat(prompt, max_tokens)

    return chat
