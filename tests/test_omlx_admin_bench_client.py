from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from local_model_runtime_evaluation.omlx_admin_bench_client import (
    BenchMetricRow,
    OmlxAdminBenchClient,
    OmlxAdminBenchError,
    build_external_bench_request,
    parse_bench_results_payload,
)


class BuildExternalBenchRequestTest(unittest.TestCase):
    def test_locked_body_shape(self) -> None:
        body = build_external_bench_request(
            model_id="Qwen3.6-35B-A3B-OptiQ-4bit",
            base_url="http://127.0.0.1:8100/v1",
            api_key="lmre-matrix-local",
        )
        self.assertEqual(body["prompt_lengths"], [1024])
        self.assertEqual(body["generation_length"], 4096)
        self.assertEqual(body["batch_sizes"], [])
        self.assertEqual(body["model_id"], "Qwen3.6-35B-A3B-OptiQ-4bit")
        external = body["external"]
        self.assertEqual(external["base_url"], "http://127.0.0.1:8100/v1")
        self.assertEqual(external["api_key"], "lmre-matrix-local")
        self.assertEqual(external["model"], "Qwen3.6-35B-A3B-OptiQ-4bit")
        self.assertEqual(
            external["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": True}},
        )


class ParseBenchResultsTest(unittest.TestCase):
    def test_parses_metric_rows(self) -> None:
        status, rows = parse_bench_results_payload({
            "status": "completed",
            "results": [{
                "ttft_ms": 12.5,
                "tpot_ms": 1.2,
                "gen_tps": 40.0,
                "e2e_latency_s": 1.5,
                "prompt_tokens": 1024,
                "completion_tokens": 200,
            }],
        })
        self.assertEqual(status, "completed")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ttft_ms, 12.5)
        self.assertEqual(rows[0].completion_tokens, 200)
        self.assertEqual(rows[0].status, "ok")


class AdminHandler(BaseHTTPRequestHandler):
    valid_api_key = "lmre-matrix-local"
    results_payload = {
        "status": "completed",
        "results": [{
            "ttft_ms": 12.5,
            "tpot_ms": 1.2,
            "gen_tps": 40.0,
            "e2e_latency_s": 1.5,
            "prompt_tokens": 1024,
            "completion_tokens": 200,
        }],
    }

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("expected JSON object")
        return payload

    def _send_json(self, status: int, payload: dict[str, object], *, cookie: str | None = None) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path == "/admin/api/login":
            payload = self._read_json()
            if payload.get("api_key") != self.valid_api_key:
                self._send_json(401, {"error": "invalid api key"})
                return
            self._send_json(200, {"ok": True}, cookie="session=bench-session; Path=/; HttpOnly")
            return
        if self.path == "/admin/api/bench/start":
            if not self.headers.get("Cookie"):
                self._send_json(401, {"error": "missing session cookie"})
                return
            self._send_json(200, {"bench_id": "bench-1"})
            return
        self.send_error(404)

    def do_GET(self) -> None:
        if self.path == "/admin/api/bench/bench-1/results":
            if not self.headers.get("Cookie"):
                self._send_json(401, {"error": "missing session cookie"})
                return
            self._send_json(200, self.results_payload)
            return
        self.send_error(404)


class AdminBenchClientHttpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AdminHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.admin_origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_login_start_results_happy_path(self) -> None:
        client = OmlxAdminBenchClient(self.admin_origin, timeout_seconds=5.0)
        client.login("lmre-matrix-local")
        body = build_external_bench_request(
            model_id="Qwen3.6-35B-A3B-OptiQ-4bit",
            base_url="http://127.0.0.1:8100/v1",
            api_key="lmre-matrix-local",
        )
        bench_id = client.start_external_bench(body)
        self.assertEqual(bench_id, "bench-1")
        status, rows = client.fetch_results(bench_id)
        self.assertEqual(status, "completed")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], BenchMetricRow(
            ttft_ms=12.5,
            tpot_ms=1.2,
            gen_tps=40.0,
            e2e_latency_s=1.5,
            prompt_tokens=1024,
            completion_tokens=200,
            status="ok",
        ))

    def test_login_401_is_fail_closed(self) -> None:
        client = OmlxAdminBenchClient(self.admin_origin, timeout_seconds=5.0)
        with self.assertRaises(OmlxAdminBenchError) as ctx:
            client.login("wrong-key")
        self.assertEqual(ctx.exception.reason, "login_failed")

    def test_bench_start_without_cookie_fails(self) -> None:
        client = OmlxAdminBenchClient(self.admin_origin, timeout_seconds=5.0)
        body = build_external_bench_request(
            model_id="Qwen3.6-35B-A3B-OptiQ-4bit",
            base_url="http://127.0.0.1:8100/v1",
            api_key="lmre-matrix-local",
        )
        with self.assertRaises(OmlxAdminBenchError) as ctx:
            client.start_external_bench(body)
        self.assertEqual(ctx.exception.reason, "bench_start_failed")


if __name__ == "__main__":
    unittest.main()
