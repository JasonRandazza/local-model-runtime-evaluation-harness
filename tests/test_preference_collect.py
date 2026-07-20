from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.matrix_servers import ServerError
from local_model_runtime_evaluation.preference_collect import (
    AnswerRecord,
    collect_cell,
    run_collect,
    write_answers,
)
from local_model_runtime_evaluation.preference_config import PreferenceSuite
from local_model_runtime_evaluation.transport import TransportError

ROOT = Path(__file__).resolve().parents[1]


def _cell(**overrides: object) -> Cell:
    data = dict(
        cell_id="jang_4m__osaurus",
        quant="jang_4m",
        server="osaurus",
        base_url="http://127.0.0.1:1337/v1",
        model_id="gemma-4-12b-it-qat-jang_4m",
        artifact_path="/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
        start_command=("true",),
        stop_command=(),
        health_path="/health",
        notes="",
    )
    data.update(overrides)
    return Cell(**data)  # type: ignore[arg-type]


class FakeProbe:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def free_memory_percent(self) -> int:
        return self.values.pop(0)


class FakeHandle:
    def start(self) -> None:
        return None

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None:
        return None

    def stop(self) -> None:
        return None


class CollectCellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = PreferenceSuite.load(ROOT / "suites/gemma-preference-v1.json")
        self.cell = _cell()
        self.log_dir = Path("/tmp/lmre-preference-test-logs")
        self.cancel = threading.Event()

    def test_collect_cell_writes_one_answer_per_prompt(self) -> None:
        chat_calls: list[str] = []

        class FakeTransport:
            def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
                return (self.cell.model_id,)

            def chat(
                self,
                base_url: str,
                model_id: str,
                prompt: str,
                max_tokens: int,
                credential: object | None,
                cancel: threading.Event,
            ) -> SimpleNamespace:
                chat_calls.append(prompt)
                return SimpleNamespace(
                    content="ok",
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        transport = FakeTransport()
        transport.cell = self.cell  # type: ignore[attr-defined]

        records = collect_cell(
            self.cell,
            self.suite,
            transport,  # type: ignore[arg-type]
            credential=None,
            build_server=lambda cell, transport, log_dir, credential: FakeHandle(),
            probe=None,
            cancel=self.cancel,
            ready_timeout=1.0,
            request_timeout=5.0,
            log_dir=self.log_dir,
        )
        self.assertEqual(len(records), 6)
        self.assertEqual(len(chat_calls), 6)
        for record in records:
            self.assertTrue(record.success)
            self.assertEqual(record.content, "ok")
            self.assertEqual(record.cell_id, self.cell.cell_id)
            self.assertEqual(record.model_id, self.cell.model_id)
            self.assertIsNone(record.error)
            self.assertEqual(record.total_seconds, 1.0)
            self.assertEqual(record.ttft_seconds, 0.2)

    def test_transport_error_continues_remaining_prompts(self) -> None:
        calls = {"count": 0}

        class FakeTransport:
            def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
                return (self.cell.model_id,)

            def chat(
                self,
                base_url: str,
                model_id: str,
                prompt: str,
                max_tokens: int,
                credential: object | None,
                cancel: threading.Event,
            ) -> SimpleNamespace:
                calls["count"] += 1
                if calls["count"] == 1:
                    raise TransportError("chat failed")
                return SimpleNamespace(
                    content="ok",
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        transport = FakeTransport()
        transport.cell = self.cell  # type: ignore[attr-defined]

        records = collect_cell(
            self.cell,
            self.suite,
            transport,  # type: ignore[arg-type]
            credential=None,
            build_server=lambda cell, transport, log_dir, credential: FakeHandle(),
            probe=None,
            cancel=self.cancel,
            ready_timeout=1.0,
            request_timeout=5.0,
            log_dir=self.log_dir,
        )
        self.assertEqual(len(records), 6)
        self.assertFalse(records[0].success)
        self.assertEqual(records[0].error, "chat failed")
        self.assertIsNone(records[0].content)
        for record in records[1:]:
            self.assertTrue(record.success)
            self.assertEqual(record.content, "ok")


class WriteAnswersTests(unittest.TestCase):
    def test_write_answers_serializes_records(self) -> None:
        records = [
            AnswerRecord(
                prompt_id="p1",
                cell_id="c1",
                model_id="m1",
                content="answer",
                success=True,
                error=None,
                total_seconds=1.0,
                ttft_seconds=0.1,
            )
        ]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "answers" / "c1.json"
            write_answers(path, "c1", "m1", records)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["cell_id"], "c1")
            self.assertEqual(payload["model_id"], "m1")
            self.assertEqual(len(payload["answers"]), 1)
            self.assertEqual(payload["answers"][0]["content"], "answer")


class RunCollectTests(unittest.TestCase):
    def test_run_collect_continues_after_server_failure(self) -> None:
        cells = (
            _cell(cell_id="jang_4m__osaurus"),
            _cell(
                cell_id="oq4_fp16__omlx",
                quant="oq4_fp16",
                server="omlx",
                base_url="http://127.0.0.1:8100/v1",
                model_id="gemma-4-12B-it-qat-oQ4-fp16",
                artifact_path="/Users/jrazz/.cache/huggingface/hub/avneetsb/gemma-4-12B-it-qat-oQ4-fp16",
            ),
        )
        fail_handle = MagicMock()
        fail_handle.wait_ready.side_effect = ServerError("unloadable")
        ok_handle = FakeHandle()
        build_server = MagicMock(side_effect=[fail_handle, ok_handle])

        class FakeTransport:
            def __init__(self, allowed_base_urls: set[str], timeout_seconds: int = 120) -> None:
                self.timeout_seconds = timeout_seconds

            def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
                return (
                    "gemma-4-12b-it-qat-jang_4m",
                    "gemma-4-12B-it-qat-oQ4-fp16",
                )

            def chat(
                self,
                base_url: str,
                model_id: str,
                prompt: str,
                max_tokens: int,
                credential: object | None,
                cancel: threading.Event,
            ) -> SimpleNamespace:
                return SimpleNamespace(
                    content="ok",
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        with TemporaryDirectory() as tmp:
            cells_root = Path(tmp) / "cells"
            cells_root.mkdir()
            for cell in cells:
                (cells_root / f"{cell.cell_id}.json").write_text(
                    json.dumps({
                        "cell_id": cell.cell_id,
                        "quant": cell.quant,
                        "server": cell.server,
                        "base_url": cell.base_url,
                        "model_id": cell.model_id,
                        "artifact_path": cell.artifact_path,
                        "start_command": list(cell.start_command),
                        "stop_command": list(cell.stop_command),
                        "health_path": cell.health_path,
                        "notes": cell.notes,
                    }),
                    encoding="utf-8",
                )

            run_dir = run_collect(
                tuple(cell.cell_id for cell in cells),
                ROOT / "suites/gemma-preference-v1.json",
                cells_root,
                Path(tmp) / "results" / "preference",
                family_id="gemma-4-12b-qat",
                build_server=build_server,
                transport_factory=FakeTransport,
                probe=FakeProbe([80, 80, 80]),
                credential_for=lambda server: None,
                ready_timeout=1.0,
                request_timeout=5.0,
                memory_floor_percent=20,
            )

            self.assertTrue(run_dir.name.startswith("gemma-preference-"))
            self.assertEqual(run_dir.parent.name, "preference")
            raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["suite_id"], "gemma-preference-v1")
            self.assertEqual(raw["cell_ids"], ["jang_4m__osaurus", "oq4_fp16__omlx"])
            self.assertEqual(raw["family_id"], "gemma-4-12b-qat")
            self.assertIn("started_at", raw)

            failed = json.loads((run_dir / "answers" / "jang_4m__osaurus.json").read_text())
            self.assertEqual(failed["answers"], [])
            self.assertEqual(failed["error"], "unloadable")

            ok = json.loads((run_dir / "answers" / "oq4_fp16__omlx.json").read_text())
            self.assertEqual(len(ok["answers"]), 6)
            self.assertTrue(all(item["success"] for item in ok["answers"]))


if __name__ == "__main__":
    unittest.main()
