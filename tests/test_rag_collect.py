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
from dataclasses import asdict

from local_model_runtime_evaluation.rag_collect import collect_cell, run_collect
from local_model_runtime_evaluation.rag_config import RagCorpus, RagError, RagSuite
from local_model_runtime_evaluation.rag_prompt import build_oracle_prompt
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


class FakeHandle:
    def start(self) -> None:
        return None

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None:
        return None

    def stop(self) -> None:
        return None


class FakeProbe:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def free_memory_percent(self) -> int:
        return self.values.pop(0)


class CollectCellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
        self.corpus = RagCorpus.load(ROOT / "corpora/rag-oracle-v1")
        self.cell = _cell()
        self.log_dir = Path("/tmp/lmre-rag-test-logs")
        self.cancel = threading.Event()

    def test_collect_writes_one_answer_per_question(self) -> None:
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
                    content=" ".join(self.question.required_facts),
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        transport = FakeTransport()
        transport.cell = self.cell  # type: ignore[attr-defined]
        transport.question = self.suite.questions[0]  # type: ignore[attr-defined]

        question_index = {"value": 0}

        def fake_chat(
            base_url: str,
            model_id: str,
            prompt: str,
            max_tokens: int,
            credential: object | None,
            cancel: threading.Event,
        ) -> SimpleNamespace:
            question = self.suite.questions[question_index["value"]]
            question_index["value"] += 1
            chat_calls.append(prompt)
            return SimpleNamespace(
                content=" ".join(question.required_facts),
                total_seconds=1.0,
                ttft_seconds=0.2,
            )

        transport.chat = fake_chat  # type: ignore[method-assign]

        records = collect_cell(
            self.cell,
            self.suite,
            self.corpus,
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
        for index, record in enumerate(records):
            question = self.suite.questions[index]
            self.assertTrue(record.success)
            self.assertEqual(record.prompt_id, question.prompt_id)
            for fact in question.required_facts:
                self.assertIn(fact, record.content or "")
            self.assertEqual(record.cell_id, self.cell.cell_id)
            self.assertEqual(record.model_id, self.cell.model_id)
            self.assertIsNone(record.error)
            expected_prompt = build_oracle_prompt(question, self.corpus)
            self.assertEqual(chat_calls[index], expected_prompt)
            self.assertIsNone(record.retrieved_chunk_ids)

    def test_collect_keyword_records_retrieved_ids(self) -> None:
        chat_calls: list[str] = []
        question_index = {"value": 0}

        class FakeTransport:
            def chat(
                self,
                base_url: str,
                model_id: str,
                prompt: str,
                max_tokens: int,
                credential: object | None,
                cancel: threading.Event,
            ) -> SimpleNamespace:
                question = self.suite.questions[question_index["value"]]
                question_index["value"] += 1
                chat_calls.append(prompt)
                return SimpleNamespace(
                    content=" ".join(question.required_facts),
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        transport = FakeTransport()
        transport.suite = self.suite  # type: ignore[attr-defined]

        records = collect_cell(
            self.cell,
            self.suite,
            self.corpus,
            transport,  # type: ignore[arg-type]
            credential=None,
            build_server=lambda cell, transport, log_dir, credential: FakeHandle(),
            probe=None,
            cancel=self.cancel,
            ready_timeout=1.0,
            request_timeout=5.0,
            log_dir=self.log_dir,
            mode="keyword",
            top_k=2,
        )
        self.assertEqual(len(records), 6)
        for record in records:
            self.assertIsNotNone(record.retrieved_chunk_ids)
            self.assertEqual(len(record.retrieved_chunk_ids or ()), 2)
            payload = asdict(record)
            self.assertIn("retrieved_chunk_ids", payload)
            self.assertEqual(len(payload["retrieved_chunk_ids"]), 2)

    def test_collect_oracle_omits_or_nulls_retrieved_ids(self) -> None:
        class FakeTransport:
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
                    content="answer",
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        records = collect_cell(
            self.cell,
            self.suite,
            self.corpus,
            FakeTransport(),  # type: ignore[arg-type]
            credential=None,
            build_server=lambda cell, transport, log_dir, credential: FakeHandle(),
            probe=None,
            cancel=self.cancel,
            ready_timeout=1.0,
            request_timeout=5.0,
            log_dir=self.log_dir,
            mode="oracle",
        )
        for record in records:
            self.assertIsNone(record.retrieved_chunk_ids)

    def test_transport_error_continues(self) -> None:
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
                question = self.suite.questions[calls["count"] - 1]
                return SimpleNamespace(
                    content=" ".join(question.required_facts),
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        transport = FakeTransport()
        transport.cell = self.cell  # type: ignore[attr-defined]
        transport.suite = self.suite  # type: ignore[attr-defined]

        records = collect_cell(
            self.cell,
            self.suite,
            self.corpus,
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
            self.assertIsNotNone(record.content)

    def test_collect_cell_rejects_unknown_mode(self) -> None:
        with self.assertRaises(RagError):
            collect_cell(
                self.cell,
                self.suite,
                self.corpus,
                object(),  # type: ignore[arg-type]
                credential=None,
                build_server=lambda *args, **kwargs: (_ for _ in ()).throw(
                    AssertionError("build_server must not run"),
                ),
                probe=None,
                cancel=self.cancel,
                ready_timeout=1.0,
                request_timeout=5.0,
                log_dir=self.log_dir,
                mode="bm25",
            )


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
        suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
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
                    content="OSAURUS_PORT=1337",
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
                ROOT / "suites/gemma-rag-oracle-v1.json",
                ROOT / "corpora/rag-oracle-v1",
                cells_root,
                Path(tmp) / "results" / "rag",
                build_server=build_server,
                transport_factory=FakeTransport,
                probe=FakeProbe([80, 80, 80]),
                credential_for=lambda server: None,
                ready_timeout=1.0,
                request_timeout=5.0,
                memory_floor_percent=20,
            )

            self.assertTrue(run_dir.name.startswith("gemma-rag-"))
            self.assertEqual(run_dir.parent.name, "rag")
            raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["suite_id"], suite.suite_id)
            self.assertEqual(raw["corpus_id"], suite.corpus_id)
            self.assertEqual(raw["cell_ids"], ["jang_4m__osaurus", "oq4_fp16__omlx"])
            self.assertIn("started_at", raw)

            failed = json.loads((run_dir / "answers" / "jang_4m__osaurus.json").read_text())
            self.assertEqual(failed["answers"], [])
            self.assertEqual(failed["error"], "unloadable")

            ok = json.loads((run_dir / "answers" / "oq4_fp16__omlx.json").read_text())
            self.assertEqual(len(ok["answers"]), 6)
            self.assertTrue(all(item["success"] for item in ok["answers"]))

    def test_run_collect_keyword_raw_includes_mode_and_top_k(self) -> None:
        cell = _cell()

        class FakeTransport:
            def __init__(self, allowed_base_urls: set[str], timeout_seconds: int = 120) -> None:
                self.timeout_seconds = timeout_seconds

            def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
                return (cell.model_id,)

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
                    content="OSAURUS_PORT=1337",
                    total_seconds=1.0,
                    ttft_seconds=0.2,
                )

        with TemporaryDirectory() as tmp:
            cells_root = Path(tmp) / "cells"
            cells_root.mkdir()
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
                (cell.cell_id,),
                ROOT / "suites/gemma-rag-oracle-v1.json",
                ROOT / "corpora/rag-oracle-v1",
                cells_root,
                Path(tmp) / "results" / "rag",
                build_server=lambda cell, transport, log_dir, credential: FakeHandle(),
                transport_factory=FakeTransport,
                probe=FakeProbe([80]),
                credential_for=lambda server: None,
                ready_timeout=1.0,
                request_timeout=5.0,
                memory_floor_percent=20,
                mode="keyword",
                top_k=2,
            )

            raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["mode"], "keyword")
            self.assertEqual(raw["top_k"], 2)

            answers = json.loads(
                (run_dir / "answers" / f"{cell.cell_id}.json").read_text(encoding="utf-8")
            )
            self.assertTrue(all("retrieved_chunk_ids" in item for item in answers["answers"]))

    def test_run_collect_rejects_unknown_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(RagError):
                run_collect(
                    ("jang_4m__osaurus",),
                    ROOT / "suites/gemma-rag-oracle-v1.json",
                    ROOT / "corpora/rag-oracle-v1",
                    ROOT / "cells",
                    Path(tmp) / "results" / "rag",
                    mode="bm25",
                )


if __name__ == "__main__":
    unittest.main()
