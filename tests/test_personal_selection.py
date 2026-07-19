from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.personal_selection import (
    Lane,
    Suite,
    render_report,
    run_lane,
    summarize,
)
from local_model_runtime_evaluation.transport import LoopbackTransport


ROOT = Path(__file__).resolve().parents[1]
LANE_NATIVE = ROOT / "config/personal-selection/lanes/gemma-4-12b-native-osaurus.json"
LANE_OPTIQ = ROOT / "config/personal-selection/lanes/gemma-4-12b-optiq-via-osaurus.json"
SUITE = ROOT / "suites/personal-selection-v1.json"


class FakeProbe:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def free_memory_percent(self) -> int:
        return self.values.pop(0)


class Handler(BaseHTTPRequestHandler):
    model_id = "gemma-4-12b-it-qat-jang_4m"
    posts = 0

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": Handler.model_id}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        Handler.posts += 1
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        prompt = payload["messages"][0]["content"]
        if "Return exactly this JSON" in prompt:
            content = '{"name":"status","arguments":{"run_id":"stage1-test","include_details":false}}'
        else:
            content = "First sentence. Second sentence."
        chunks = [
            {
                "choices": [{"delta": {"content": content}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 8},
            },
        ]
        body = "".join(f"data: {json.dumps(item)}\n\n" for item in chunks) + "data: [DONE]\n\n"
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class PersonalSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        Handler.model_id = "gemma-4-12b-it-qat-jang_4m"
        Handler.posts = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_lane_and_suite_configs_load(self) -> None:
        native = Lane.load(LANE_NATIVE)
        optiq = Lane.load(LANE_OPTIQ)
        suite = Suite.load(SUITE)
        self.assertEqual(native.model_id, "gemma-4-12b-it-qat-jang_4m")
        self.assertTrue(optiq.model_id.startswith("optiq/"))
        self.assertEqual(len(suite.workloads), 3)

    def test_screen_run_writes_raw_and_report_without_secrets(self) -> None:
        lane = Lane(
            "test-lane", "gemma-4-12b-it-qat", "native-best-stack", "native",
            self.base_url, "gemma-4-12b-it-qat-jang_4m", "test", "test",
        )
        with TemporaryDirectory() as tmp:
            run_dir = run_lane(
                lane, Suite.load(SUITE), "screen", Path(tmp) / "results",
                transport=LoopbackTransport({self.base_url}),
                resource_probe=FakeProbe([80, 79]),
            )
            raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertEqual(Handler.posts, 12)
            self.assertEqual(raw["summary"]["measured_count"], 9)
            self.assertEqual(raw["summary"]["success_count"], 9)
            self.assertEqual(raw["summary"]["contract_pass_count"], 9)
            self.assertEqual(raw["memory_free_percent_before"], 80)
            self.assertEqual(raw["memory_free_percent_after"], 79)
            self.assertIn("native-best-stack", report)
            self.assertNotIn("Bearer", report)
            self.assertNotIn("Authorization", json.dumps(raw))

    def test_missing_model_fails_closed_without_posts(self) -> None:
        Handler.model_id = "something-else"
        lane = Lane(
            "test", "gemma", "native-best-stack", "native", self.base_url,
            "gemma-4-12b-it-qat-jang_4m", "hint", "notes",
        )
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(Exception, "exact model id"):
                run_lane(
                    lane, Suite.load(SUITE), "screen", Path(tmp) / "results",
                    transport=LoopbackTransport({self.base_url}),
                    resource_probe=FakeProbe([80, 79]),
                )
            self.assertEqual(Handler.posts, 0)

    def test_summarize_and_report_helpers(self) -> None:
        self.assertEqual(summarize(())["measured_count"], 0)
        text = render_report({
            "lane": {
                "lane_id": "x", "family": "f", "path_type": "native",
                "model_id": "m", "comparison_class": "native-best-stack",
            },
            "mode": "screen", "suite_id": "s", "suite_revision": "1",
            "started_at": "t0", "finished_at": "t1",
            "memory_free_percent_before": 80, "memory_free_percent_after": 79,
            "summary": {
                "measured_count": 0, "success_count": 0, "contract_pass_count": 0,
                "median_total_seconds": None, "by_workload": {},
            },
        })
        self.assertIn("Personal Model Selection Draft Report", text)
        self.assertTrue(LANE_NATIVE.exists())
        self.assertTrue(LANE_OPTIQ.exists())


if __name__ == "__main__":
    unittest.main()
