from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .credentials import Credential
from .matrix_servers import MATRIX_OMLX_API_KEY
from .omlx_thinking_pin import OmlxThinkingPin
from .token_counter import try_model_dir_token_counter
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
        chat_template_kwargs: Mapping[str, object] | None = None,
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
    reasoning_tokens: int | None = None
    visible_output_tokens: int | None = None
    token_accounting_status: str = "INCOMPARABLE_TOKEN_ACCOUNTING"
    content_span_seconds: float = 0.0
    streaming_semantics: str = "incremental"


@dataclass(repr=False)
class OmlxThinkingTransport:
    base_url: str
    model_id: str
    credential: Credential
    loopback: LoopbackClient
    chat_template_kwargs: Mapping[str, object] = field(default_factory=dict)

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
        if loopback is None:
            counter = try_model_dir_token_counter(pin.model_dir)
            client: LoopbackClient = LoopbackTransport(
                {pin.base_url},
                timeout_seconds=timeout_seconds,
                token_counter=counter,
            )
        else:
            client = loopback
        return cls(
            pin.base_url,
            pin.model_id,
            resolved,
            client,
            dict(pin.required_chat_template_kwargs),
        )

    def list_models(self) -> tuple[str, ...]:
        return self.loopback.list_models(self.base_url, self.credential)

    def chat(self, prompt: str, max_tokens: int) -> ThinkingChatResponse:
        result = self.loopback.chat(
            self.base_url,
            self.model_id,
            prompt,
            max_tokens,
            self.credential,
            chat_template_kwargs=self.chat_template_kwargs or None,
        )
        streaming_semantics = (
            "incremental"
            if bool(getattr(result, "stream_valid", False))
            and int(getattr(result, "content_event_count", 0) or 0) > 0
            else "buffered"
        )
        content_span = float(getattr(result, "last_content_seconds", 0.0) or 0.0)
        return ThinkingChatResponse(
            visible_text=str(result.content),
            finish_reason=result.finish_reason,
            reasoning_tokens=getattr(result, "reasoning_tokens", None),
            visible_output_tokens=getattr(result, "visible_output_tokens", None),
            token_accounting_status=str(
                getattr(result, "token_accounting_status", "INCOMPARABLE_TOKEN_ACCOUNTING")
            ),
            content_span_seconds=content_span,
            streaming_semantics=streaming_semantics,
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
