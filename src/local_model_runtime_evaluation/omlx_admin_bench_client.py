from __future__ import annotations

import http.client
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class OmlxAdminBenchError(RuntimeError):
    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class BenchMetricRow:
    ttft_ms: float | None
    tpot_ms: float | None
    gen_tps: float | None
    e2e_latency_s: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    status: str
    error: str | None = None


def build_external_bench_request(
    *,
    model_id: str,
    base_url: str,
    api_key: str,
    enable_thinking: bool = True,
) -> dict[str, object]:
    return {
        "model_id": model_id,
        "prompt_lengths": [1024],
        "generation_length": 4096,
        "batch_sizes": [],
        "external": {
            "base_url": base_url,
            "api_key": api_key,
            "model": model_id,
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": enable_thinking},
            },
        },
    }


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def parse_bench_results_payload(payload: dict[str, object]) -> tuple[str, tuple[BenchMetricRow, ...]]:
    run_status = str(payload.get("status", ""))
    results = payload.get("results")
    if not isinstance(results, list):
        return run_status, ()
    rows: list[BenchMetricRow] = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        error = entry.get("error")
        error_str = str(error) if error is not None else None
        status = entry.get("status")
        if status is not None:
            row_status = str(status)
        elif error_str is not None:
            row_status = "error"
        else:
            row_status = "ok"
        rows.append(
            BenchMetricRow(
                ttft_ms=_optional_float(entry.get("ttft_ms")),
                tpot_ms=_optional_float(entry.get("tpot_ms")),
                gen_tps=_optional_float(entry.get("gen_tps")),
                e2e_latency_s=_optional_float(entry.get("e2e_latency_s")),
                prompt_tokens=_optional_int(entry.get("prompt_tokens")),
                completion_tokens=_optional_int(entry.get("completion_tokens")),
                status=row_status,
                error=error_str,
            )
        )
    return run_status, tuple(rows)


class OmlxAdminBenchClient:
    _ALLOWED_HOST = "127.0.0.1"

    def __init__(self, admin_origin: str = "http://127.0.0.1:8100", timeout_seconds: float = 120.0) -> None:
        parsed = urlparse(admin_origin)
        if parsed.scheme != "http" or parsed.hostname != self._ALLOWED_HOST or not parsed.port:
            raise OmlxAdminBenchError(
                "admin origin must be loopback HTTP",
                reason="endpoint_forbidden",
            )
        self._host = parsed.hostname
        self._port = parsed.port
        self._timeout_seconds = timeout_seconds
        self._cookie: str | None = None

    def _connection(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self._host, self._port, timeout=self._timeout_seconds)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        require_cookie: bool = False,
        error_reason: str,
    ) -> dict[str, Any]:
        payload = json.dumps(body).encode() if body is not None else None
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if require_cookie:
            if not self._cookie:
                raise OmlxAdminBenchError("admin session cookie missing", reason=error_reason)
            headers["Cookie"] = self._cookie
        connection = self._connection()
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            if response.status >= 400:
                raise OmlxAdminBenchError(
                    f"admin request failed with HTTP {response.status}",
                    reason=error_reason,
                )
            if not raw:
                return {}
            parsed = json.loads(raw.decode())
            if not isinstance(parsed, dict):
                raise OmlxAdminBenchError("admin response was not a JSON object", reason=error_reason)
            return parsed
        except OmlxAdminBenchError:
            raise
        except Exception as error:
            raise OmlxAdminBenchError(str(error), reason=error_reason) from error
        finally:
            connection.close()

    def login(self, api_key: str) -> None:
        connection = self._connection()
        try:
            body = json.dumps({"api_key": api_key}).encode()
            connection.request(
                "POST",
                "/admin/api/login",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            response.read()
            if response.status >= 400:
                raise OmlxAdminBenchError(
                    f"admin login failed with HTTP {response.status}",
                    reason="login_failed",
                )
            cookie_header = response.getheader("Set-Cookie")
            if not cookie_header:
                raise OmlxAdminBenchError("admin login did not return a session cookie", reason="login_failed")
            self._cookie = cookie_header.split(";", 1)[0]
        except OmlxAdminBenchError:
            raise
        except Exception as error:
            raise OmlxAdminBenchError(str(error), reason="login_failed") from error
        finally:
            connection.close()

    def start_external_bench(self, body: dict[str, object]) -> str:
        parsed = self._request(
            "POST",
            "/admin/api/bench/start",
            body=body,
            require_cookie=True,
            error_reason="bench_start_failed",
        )
        bench_id = parsed.get("bench_id")
        if not isinstance(bench_id, str) or not bench_id:
            raise OmlxAdminBenchError("bench start did not return bench_id", reason="bench_start_failed")
        return bench_id

    def fetch_results(self, bench_id: str) -> tuple[str, tuple[BenchMetricRow, ...]]:
        parsed = self._request(
            "GET",
            f"/admin/api/bench/{bench_id}/results",
            require_cookie=True,
            error_reason="results_failed",
        )
        return parse_bench_results_payload(parsed)

    def wait_for_results(
        self,
        bench_id: str,
        *,
        timeout_seconds: float = 7200.0,
        poll_seconds: float = 2.0,
    ) -> tuple[str, tuple[BenchMetricRow, ...]]:
        """Poll /results until terminal status or timeout."""
        deadline = time.monotonic() + float(timeout_seconds)
        last_status = "running"
        last_rows: tuple[BenchMetricRow, ...] = ()
        while True:
            last_status, last_rows = self.fetch_results(bench_id)
            if last_status in {"completed", "error", "cancelled"}:
                return last_status, last_rows
            if time.monotonic() >= deadline:
                raise OmlxAdminBenchError(
                    f"bench {bench_id} still {last_status!r} after {timeout_seconds}s",
                    reason="results_failed",
                )
            time.sleep(max(float(poll_seconds), 0.25))
