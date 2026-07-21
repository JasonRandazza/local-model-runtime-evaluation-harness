from __future__ import annotations

import hashlib
import http.client
import json
import select
import threading
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

from .credentials import Credential


class TransportError(RuntimeError):
    code = "transport_failed"

    def __init__(
        self,
        message: str,
        *,
        reason: str = "transport_failed",
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.http_status = http_status


@dataclass(frozen=True)
class TransportResult:
    content: str
    content_sha256: str
    ttft_seconds: float
    total_seconds: float
    completion_tokens: int | None
    finish_reason: str | None
    http_status: int
    stream_valid: bool
    content_event_count: int
    last_content_seconds: float
    reasoning_tokens: int | None
    visible_output_tokens: int | None
    token_accounting_status: str


class LoopbackTransport:
    def __init__(self, allowed_base_urls: set[str], timeout_seconds: int = 120) -> None:
        self.allowed_base_urls = frozenset(url.rstrip("/") for url in allowed_base_urls)
        self.timeout_seconds = timeout_seconds

    def _parts(self, base_url: str) -> tuple[str, int, str]:
        normalized = base_url.rstrip("/")
        if normalized not in self.allowed_base_urls:
            raise TransportError("endpoint is not approved", reason="endpoint_forbidden")
        parsed = urlparse(normalized)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path != "/v1":
            raise TransportError("endpoint must be approved loopback HTTP", reason="endpoint_forbidden")
        return parsed.hostname, parsed.port, parsed.path

    def _connection(self, base_url: str) -> tuple[http.client.HTTPConnection, str]:
        host, port, path = self._parts(base_url)
        return http.client.HTTPConnection(host, port, timeout=self.timeout_seconds), path

    @staticmethod
    def _headers(credential: Credential | None) -> dict[str, str]:
        return {} if credential is None else {"Authorization": credential.authorization_header()}

    @staticmethod
    def _call_before_deadline(
        call: Callable[[], object], connection: http.client.HTTPConnection, deadline: float,
        cancel: threading.Event | None,
    ) -> object:
        result: list[object] = []
        errors: list[BaseException] = []
        completed = threading.Event()

        def run() -> None:
            try:
                result.append(call())
            except BaseException as error:
                errors.append(error)
            finally:
                completed.set()

        threading.Thread(target=run, daemon=True).start()
        while not completed.wait(min(0.1, max(0.0, deadline - time.monotonic()))):
            if cancel is not None and cancel.is_set():
                connection.close()
                raise TransportError("request cancelled", reason="cancelled")
            if time.monotonic() >= deadline:
                connection.close()
                raise TransportError("request timed out", reason="timeout")
        if cancel is not None and cancel.is_set():
            raise TransportError("request cancelled", reason="cancelled")
        if time.monotonic() >= deadline:
            raise TransportError("request timed out", reason="timeout")
        if errors:
            raise errors[0]
        return result[0]

    def list_models(self, base_url: str, credential: Credential | None) -> tuple[str, ...]:
        connection, path = self._connection(base_url)
        try:
            connection.request("GET", f"{path}/models", headers=self._headers(credential))
            response = connection.getresponse()
            body = response.read()
            if response.status != 200:
                raise TransportError(f"model inventory returned HTTP {response.status}", reason="http_status", http_status=response.status)
            payload = json.loads(body)
            return tuple(str(item["id"]) for item in payload["data"])
        except (OSError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise TransportError("model inventory failed", reason="inventory_failed") from error
        finally:
            connection.close()

    def health(self, base_url: str) -> dict[str, object]:
        connection, _ = self._connection(base_url)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            body = response.read()
            if response.status != 200:
                raise TransportError(f"health returned HTTP {response.status}", reason="http_status", http_status=response.status)
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise TransportError("health payload is not an object", reason="health_invalid")
            return payload
        except TransportError:
            raise
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            raise TransportError("health probe failed", reason="health_failed") from error
        finally:
            connection.close()

    def chat(
        self, base_url: str, model_id: str, prompt: str, max_tokens: int,
        credential: Credential | None, cancel: threading.Event | None = None,
    ) -> TransportResult:
        connection, path = self._connection(base_url)
        payload = json.dumps({
            "model": model_id, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True},
        }).encode()
        started = time.monotonic()
        deadline = started + self.timeout_seconds
        first_token: float | None = None
        content: list[str] = []
        content_event_count = 0
        last_content: float | None = None
        finish_reason: str | None = None
        completion_tokens: int | None = None
        reasoning_tokens: int | None = None
        try:
            headers = self._headers(credential)
            headers["Content-Type"] = "application/json"
            if cancel is not None and cancel.is_set():
                raise TransportError("request cancelled", reason="cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError("request timed out", reason="timeout")
            connection.timeout = remaining
            self._call_before_deadline(
                lambda: connection.request(
                    "POST", f"{path}/chat/completions", body=payload, headers=headers
                ),
                connection,
                deadline,
                cancel,
            )
            if cancel is not None and cancel.is_set():
                raise TransportError("request cancelled", reason="cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError("request timed out", reason="timeout")
            request_socket = getattr(connection, "sock", None)
            if request_socket is not None:
                request_socket.settimeout(remaining)
            response = self._call_before_deadline(
                connection.getresponse, connection, deadline, cancel
            )
            if response.status != 200:
                self._call_before_deadline(response.read, connection, deadline, cancel)
                raise TransportError(f"chat request returned HTTP {response.status}", reason="http_status", http_status=response.status)
            if "text/event-stream" not in response.getheader("Content-Type", ""):
                raise TransportError("chat response is not an SSE stream", reason="not_sse")
            stream_socket = connection.sock
            if stream_socket is None:
                stream_socket = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            if stream_socket is None:
                raise TransportError("chat stream failed", reason="stream_setup_failed")
            stream_reader = getattr(response, "fp", None)
            if stream_reader is None or not hasattr(stream_reader, "read1"):
                raise TransportError("chat stream failed", reason="stream_setup_failed")
            pending = bytearray()
            stream_done = False
            # Never apply a short socket timeout to the stream makefile: after a
            # TimeoutError, Python's socket makefile permanently raises
            # OSError("cannot read from timed out object") on later peeks/reads.
            # Wait with select() instead so OptiQ prompt-processing keepalives
            # that arrive >1s after headers do not abort the cohort.
            stream_socket.settimeout(None)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TransportError("request timed out", reason="timeout")
                if cancel is not None and cancel.is_set():
                    raise TransportError("request cancelled", reason="cancelled")
                stream_socket.settimeout(0)
                try:
                    buffered = stream_reader.peek(1)
                except (BlockingIOError, InterruptedError, TimeoutError):
                    buffered = b""
                finally:
                    stream_socket.settimeout(None)
                if not buffered:
                    readable, _, _ = select.select([stream_socket], [], [], min(1.0, remaining))
                    if not readable:
                        continue
                try:
                    chunk = stream_reader.read1(4096)
                except (BlockingIOError, InterruptedError, TimeoutError):
                    continue
                if not chunk:
                    break
                pending.extend(chunk)
                while b"\n" in pending:
                    newline = pending.index(b"\n")
                    line = bytes(pending[:newline])
                    del pending[:newline + 1]
                    decoded = line.decode("utf-8")
                    if decoded in ("", "\r") or decoded.startswith(":"):
                        continue
                    if not decoded.startswith("data: "):
                        raise TransportError("unsupported SSE framing", reason="unsupported_sse")
                    data = decoded[6:].rstrip()
                    if data == "[DONE]":
                        stream_done = True
                        break
                    event = json.loads(data)
                    choices = event.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {}).get("content")
                        if delta:
                            if first_token is None:
                                first_token = time.monotonic()
                            last_content = time.monotonic()
                            content_event_count += 1
                            content.append(str(delta))
                        if choices[0].get("finish_reason") is not None:
                            finish_reason = str(choices[0]["finish_reason"])
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        completion_value = usage.get("completion_tokens")
                        if completion_value is not None:
                            if (
                                not isinstance(completion_value, int)
                                or isinstance(completion_value, bool)
                                or completion_value < 0
                            ):
                                raise TransportError("completion-token accounting is invalid", reason="invalid_token_accounting")
                            completion_tokens = completion_value
                        details = usage.get("completion_tokens_details")
                        if isinstance(details, dict) and "reasoning_tokens" in details:
                            reasoning_value = details["reasoning_tokens"]
                            if (
                                not isinstance(reasoning_value, int)
                                or isinstance(reasoning_value, bool)
                                or reasoning_value < 0
                            ):
                                raise TransportError("reasoning-token accounting is invalid", reason="invalid_token_accounting")
                            reasoning_tokens = reasoning_value
                if stream_done:
                    break
            if not stream_done:
                raise TransportError("incomplete SSE stream", reason="incomplete_sse")
        except TransportError:
            raise
        except TimeoutError as error:
            if cancel is not None and cancel.is_set():
                raise TransportError("request cancelled", reason="cancelled") from error
            raise TransportError("request timed out", reason="timeout") from error
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise TransportError("chat stream failed", reason="stream_failed") from error
        finally:
            connection.close()
        ended = time.monotonic()
        if first_token is None:
            raise TransportError("chat stream produced no content", reason="empty_content")
        if last_content is None:
            raise TransportError("chat stream content timing is unavailable", reason="content_timing_unavailable")
        visible_output_tokens: int | None = None
        token_accounting_status = "INCOMPARABLE_TOKEN_ACCOUNTING"
        if completion_tokens is not None and reasoning_tokens is not None:
            if reasoning_tokens > completion_tokens:
                raise TransportError("reasoning tokens exceed total completion tokens", reason="invalid_token_accounting")
            visible_output_tokens = completion_tokens - reasoning_tokens
            if visible_output_tokens <= 0:
                raise TransportError("visible output token count is invalid", reason="invalid_token_accounting")
            token_accounting_status = "EXACT_VISIBLE"
        joined = "".join(content)
        return TransportResult(
            joined, hashlib.sha256(joined.encode()).hexdigest(), first_token - started,
            ended - started, completion_tokens, finish_reason, 200, True,
            content_event_count, last_content - started, reasoning_tokens,
            visible_output_tokens, token_accounting_status,
        )
