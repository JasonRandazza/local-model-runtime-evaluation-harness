from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any

from local_model_runtime_evaluation.matrix_config import Cell, load_family
from local_model_runtime_evaluation.preference_config import (
    PreferenceError,
    PreferencePrompt,
    PreferenceSuite,
)
from local_model_runtime_evaluation.preference_judge import (
    DEFAULT_JUDGE_CELL,
    REASON_MAX_CHARS,
    build_judge_prompt,
    load_pairs,
    parse_judge_response,
    run_judge,
)
from local_model_runtime_evaluation.transport import TransportError

ROOT = Path(__file__).resolve().parents[1]
CELLS_ROOT = ROOT / "config/matrix/cells"
JUDGE_CELL_ID = DEFAULT_JUDGE_CELL

_TEST_SUITE = PreferenceSuite(
    suite_id="test-suite",
    revision="1",
    prompts=(
        PreferencePrompt("p1", "First prompt.", 256),
        PreferencePrompt("p2", "Second prompt.", 256),
    ),
)


def _write_answers(
    answers_dir: Path,
    cell_id: str,
    prompt_ids: tuple[str, ...],
) -> None:
    payload = {
        "cell_id": cell_id,
        "model_id": "model-x",
        "answers": [
            {
                "prompt_id": prompt_id,
                "cell_id": cell_id,
                "model_id": "model-x",
                "content": f"Answer for {prompt_id} from {cell_id}.",
                "success": True,
                "error": None,
                "total_seconds": 1.0,
                "ttft_seconds": 0.1,
            }
            for prompt_id in prompt_ids
        ],
    }
    answers_dir.mkdir(parents=True, exist_ok=True)
    (answers_dir / f"{cell_id}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_run_dir(
    run_dir: Path,
    *,
    pairs: list[dict[str, str]],
    prompt_ids: tuple[str, ...] = ("p1", "p2"),
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pairs.json").write_text(
        json.dumps({"pairs": pairs}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    answers_dir = run_dir / "answers"
    cell_ids = {pair["cell_a"] for pair in pairs} | {pair["cell_b"] for pair in pairs}
    for cell_id in sorted(cell_ids):
        _write_answers(answers_dir, cell_id, prompt_ids)
    (run_dir / "raw.json").write_text(
        json.dumps({"suite_id": "test-suite"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class FakeHandle:
    def start(self) -> None:
        return None

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None:
        return None

    def stop(self) -> None:
        return None


class FakeTransport:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def chat(
        self,
        base_url: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        credential: object | None,
        cancel: threading.Event,
    ) -> SimpleNamespace:
        del base_url, model_id, prompt, credential, cancel
        if self.calls >= len(self._responses):
            raise AssertionError("unexpected chat call")
        response = self._responses[self.calls]
        self.calls += 1
        if isinstance(response, BaseException):
            raise response
        return SimpleNamespace(
            content=response,
            total_seconds=1.0,
            ttft_seconds=0.1,
        )


class PreferenceJudgeParseTests(unittest.TestCase):
    def test_default_judge_cell(self) -> None:
        self.assertEqual(DEFAULT_JUDGE_CELL, "jang_4m__osaurus")

    def test_parse_happy_path(self) -> None:
        result = parse_judge_response('{"winner": "A", "reason": "Clearer structure."}')
        self.assertEqual(result["winner"], "A")
        self.assertEqual(result["reason"], "Clearer structure.")

    def test_parse_winner_only(self) -> None:
        result = parse_judge_response('{"winner": "tie"}')
        self.assertEqual(result["winner"], "tie")
        self.assertIsNone(result["reason"])

    def test_parse_rejects_invalid_winner(self) -> None:
        with self.assertRaises(PreferenceError):
            parse_judge_response('{"winner": "C"}')

    def test_parse_rejects_lowercase_winner(self) -> None:
        with self.assertRaises(PreferenceError):
            parse_judge_response('{"winner": "a"}')

    def test_parse_fenced_includes_reason(self) -> None:
        text = '```json\n{"winner": "B", "reason": "More concrete."}\n```'
        result = parse_judge_response(text)
        self.assertEqual(result["winner"], "B")
        self.assertEqual(result["reason"], "More concrete.")

    def test_parse_rejects_malformed_json(self) -> None:
        with self.assertRaises(PreferenceError):
            parse_judge_response("not json")

    def test_parse_extracts_json_object_from_fenced_text(self) -> None:
        # Model may wrap JSON in prose or fences; extract first {...} object
        text = 'Here is my verdict:\n```json\n{"winner": "B", "reason": "More concrete."}\n```'
        result = parse_judge_response(text)
        self.assertEqual(result["winner"], "B")

    def test_reason_truncated(self) -> None:
        long_reason = "x" * (REASON_MAX_CHARS + 50)
        result = parse_judge_response(
            '{"winner": "A", "reason": "' + long_reason + '"}'
        )
        self.assertEqual(len(result["reason"] or ""), REASON_MAX_CHARS)

    def test_build_judge_prompt_hides_cell_ids(self) -> None:
        prompt = build_judge_prompt(
            "Explain tradeoffs.",
            "Answer text A mentioning nothing sensitive.",
            "Answer text B.",
        )
        self.assertIn("Explain tradeoffs.", prompt)
        self.assertIn("Answer text A", prompt)
        self.assertIn("Answer text B", prompt)
        self.assertNotIn("jang_4m", prompt)
        self.assertNotIn("osaurus", prompt)
        self.assertIn('"winner"', prompt)


class LoadPairsTests(unittest.TestCase):
    def test_load_pairs_rejects_invalid_pair_shape(self) -> None:
        invalid_pairs = [
            {"foo": 1},
            {"pair_id": "p1__00", "prompt_id": "p1"},
            "not-a-dict",
        ]
        for index, pair in enumerate(invalid_pairs):
            with self.subTest(index=index, pair=pair):
                with TemporaryDirectory() as tmp:
                    run_dir = Path(tmp) / "run"
                    run_dir.mkdir()
                    (run_dir / "pairs.json").write_text(
                        json.dumps({"pairs": [pair]}, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(PreferenceError):
                        load_pairs(run_dir)


class RunJudgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cancel = threading.Event()
        self.judge_cell = Cell.load(
            CELLS_ROOT / f"{JUDGE_CELL_ID}.json",
            family=load_family("gemma-4-12b-qat"),
        )

    def _run(
        self,
        run_dir: Path,
        transport: FakeTransport,
        *,
        pairs: list[dict[str, str]] | None = None,
    ) -> Path:
        if pairs is not None:
            _write_run_dir(run_dir, pairs=pairs)
        return run_judge(
            run_dir,
            judge_cell_id=JUDGE_CELL_ID,
            cells_root=CELLS_ROOT,
            suite=_TEST_SUITE,
            family_id="gemma-4-12b-qat",
            build_server=lambda cell, transport_arg, log_dir, credential: FakeHandle(),
            transport_factory=lambda base_urls, timeout: transport,  # type: ignore[return-value]
            credential_for=lambda server: None,
            ready_timeout=1.0,
            request_timeout=5.0,
            cancel=self.cancel,
        )

    def test_run_judge_fills_judgments(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            pairs = [
                {
                    "pair_id": "p1__00",
                    "prompt_id": "p1",
                    "cell_a": "cell_a",
                    "cell_b": "cell_b",
                },
                {
                    "pair_id": "p2__00",
                    "prompt_id": "p2",
                    "cell_a": "cell_a",
                    "cell_b": "cell_b",
                },
            ]
            _write_run_dir(run_dir, pairs=pairs)
            transport = FakeTransport(
                ['{"winner":"A","reason":"ok"}'] * 2,
            )
            self._run(run_dir, transport)

            judgments = json.loads((run_dir / "judgments.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["winner"] for item in judgments["judgments"]],
                ["A", "A"],
            )
            judge_raw = json.loads((run_dir / "judge_raw.json").read_text(encoding="utf-8"))
            self.assertEqual(judge_raw["judge_cell_id"], JUDGE_CELL_ID)
            raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["judge_cell_id"], JUDGE_CELL_ID)
            self.assertIn("judged_at", raw)

    def test_run_judge_retries_once_then_null(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            pairs = [
                {
                    "pair_id": "p1__00",
                    "prompt_id": "p1",
                    "cell_a": "cell_a",
                    "cell_b": "cell_b",
                },
            ]
            _write_run_dir(run_dir, pairs=pairs)
            transport = FakeTransport(["not json", "not json"])
            self._run(run_dir, transport)

            judgments = json.loads((run_dir / "judgments.json").read_text(encoding="utf-8"))
            self.assertIsNone(judgments["judgments"][0]["winner"])
            judge_raw = json.loads((run_dir / "judge_raw.json").read_text(encoding="utf-8"))
            self.assertEqual(len(judge_raw["pairs"][0]["attempts"]), 2)
            self.assertFalse(judge_raw["pairs"][0]["attempts"][0]["ok"])
            self.assertFalse(judge_raw["pairs"][0]["attempts"][1]["ok"])

    def test_run_judge_retry_succeeds(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            pairs = [
                {
                    "pair_id": "p1__00",
                    "prompt_id": "p1",
                    "cell_a": "cell_a",
                    "cell_b": "cell_b",
                },
            ]
            _write_run_dir(run_dir, pairs=pairs)
            transport = FakeTransport(
                ["not json", '{"winner":"B","reason":"better"}'],
            )
            self._run(run_dir, transport)

            judgments = json.loads((run_dir / "judgments.json").read_text(encoding="utf-8"))
            self.assertEqual(judgments["judgments"][0]["winner"], "B")
            judge_raw = json.loads((run_dir / "judge_raw.json").read_text(encoding="utf-8"))
            self.assertEqual(len(judge_raw["pairs"][0]["attempts"]), 2)
            self.assertFalse(judge_raw["pairs"][0]["attempts"][0]["ok"])
            self.assertTrue(judge_raw["pairs"][0]["attempts"][1]["ok"])
            self.assertEqual(judge_raw["pairs"][0]["winner"], "B")

    def test_run_judge_transport_error_retries_then_null(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            pairs = [
                {
                    "pair_id": "p1__00",
                    "prompt_id": "p1",
                    "cell_a": "cell_a",
                    "cell_b": "cell_b",
                },
            ]
            _write_run_dir(run_dir, pairs=pairs)
            transport = FakeTransport(
                [TransportError("chat failed"), TransportError("chat failed again")],
            )
            self._run(run_dir, transport)

            judgments = json.loads((run_dir / "judgments.json").read_text(encoding="utf-8"))
            self.assertIsNone(judgments["judgments"][0]["winner"])
            judge_raw = json.loads((run_dir / "judge_raw.json").read_text(encoding="utf-8"))
            self.assertEqual(len(judge_raw["pairs"][0]["attempts"]), 2)


if __name__ == "__main__":
    unittest.main()
