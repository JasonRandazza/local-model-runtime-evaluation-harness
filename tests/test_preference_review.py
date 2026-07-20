from __future__ import annotations

import json
import random
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.preference_config import (
    DEFAULT_PREFERENCE_CELLS,
    PreferenceError,
    PreferenceSuite,
)
from local_model_runtime_evaluation.preference_review import (
    build_pairs,
    write_review,
)

ROOT = Path(__file__).resolve().parents[1]


def _prompt_ids() -> tuple[str, ...]:
    suite = PreferenceSuite.load(ROOT / "suites/gemma-preference-v1.json")
    return tuple(prompt.prompt_id for prompt in suite.prompts)


def _prompts_by_id() -> dict[str, str]:
    suite = PreferenceSuite.load(ROOT / "suites/gemma-preference-v1.json")
    return {prompt.prompt_id: prompt.prompt for prompt in suite.prompts}


def _answers_by_cell() -> dict[str, dict]:
    suite = PreferenceSuite.load(ROOT / "suites/gemma-preference-v1.json")
    answers: dict[str, dict] = {}
    for index, cell_id in enumerate(DEFAULT_PREFERENCE_CELLS):
        answers[cell_id] = {
            "cell_id": cell_id,
            "model_id": f"model-{index}",
            "answers": [
                {
                    "prompt_id": prompt.prompt_id,
                    "cell_id": cell_id,
                    "model_id": f"model-{index}",
                    "content": f"Answer for {prompt.prompt_id} (variant {index + 1}).",
                    "success": True,
                    "error": None,
                    "total_seconds": 1.0,
                    "ttft_seconds": 0.1,
                }
                for prompt in suite.prompts
            ],
        }
    return answers


class BuildPairsTests(unittest.TestCase):
    def test_build_pairs_count_is_thirty_six(self) -> None:
        pairs = build_pairs(
            DEFAULT_PREFERENCE_CELLS,
            _prompt_ids(),
            rng=random.Random(0),
        )
        self.assertEqual(len(pairs), 36)

    def test_build_pairs_unique_pair_ids(self) -> None:
        pairs = build_pairs(
            DEFAULT_PREFERENCE_CELLS,
            _prompt_ids(),
            rng=random.Random(0),
        )
        pair_ids = [pair["pair_id"] for pair in pairs]
        self.assertEqual(len(pair_ids), len(set(pair_ids)))

    def test_build_pairs_deterministic_for_fixed_seed(self) -> None:
        kwargs = {
            "cell_ids": DEFAULT_PREFERENCE_CELLS,
            "prompt_ids": _prompt_ids(),
        }
        first = build_pairs(**kwargs, rng=random.Random(42))
        second = build_pairs(**kwargs, rng=random.Random(42))
        self.assertEqual(first, second)

    def test_build_pairs_expected_keys(self) -> None:
        pairs = build_pairs(
            DEFAULT_PREFERENCE_CELLS,
            _prompt_ids(),
            rng=random.Random(0),
        )
        for pair in pairs:
            self.assertEqual(
                set(pair),
                {"pair_id", "prompt_id", "cell_a", "cell_b"},
            )
            self.assertNotIn("answer_a", pair)
            self.assertNotIn("answer_b", pair)


class WriteReviewTests(unittest.TestCase):
    def test_review_hides_cell_ids_in_markdown_body(self) -> None:
        pairs = build_pairs(
            DEFAULT_PREFERENCE_CELLS,
            _prompt_ids(),
            rng=random.Random(0),
        )
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_review(
                run_dir,
                pairs,
                _answers_by_cell(),
                _prompts_by_id(),
            )
            review = (run_dir / "review.md").read_text(encoding="utf-8")
            self.assertIn("**A**", review)
            self.assertIn("**B**", review)
            self.assertIn("Do not look up cell ids", review)
            for cell_id in DEFAULT_PREFERENCE_CELLS:
                self.assertNotIn(cell_id, review)

    def test_judgments_stub_null_winners(self) -> None:
        pairs = build_pairs(
            DEFAULT_PREFERENCE_CELLS,
            _prompt_ids(),
            rng=random.Random(0),
        )
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_review(
                run_dir,
                pairs,
                _answers_by_cell(),
                _prompts_by_id(),
            )
            payload = json.loads((run_dir / "judgments.json").read_text(encoding="utf-8"))
            self.assertIn("judgments", payload)
            self.assertEqual(len(payload["judgments"]), 36)
            for item in payload["judgments"]:
                self.assertIsNone(item["winner"])
                self.assertIn("pair_id", item)

    def test_pairs_json_maps_cells_without_answer_bodies(self) -> None:
        pairs = build_pairs(
            DEFAULT_PREFERENCE_CELLS,
            _prompt_ids(),
            rng=random.Random(0),
        )
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_review(
                run_dir,
                pairs,
                _answers_by_cell(),
                _prompts_by_id(),
            )
            saved = json.loads((run_dir / "pairs.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["pairs"], pairs)
            for pair in saved["pairs"]:
                self.assertNotIn("answer_a", pair)
                self.assertNotIn("answer_b", pair)

    def test_missing_answer_raises_preference_error(self) -> None:
        pairs = build_pairs(
            DEFAULT_PREFERENCE_CELLS,
            ("tradeoff-explain",),
            rng=random.Random(0),
        )
        answers = _answers_by_cell()
        answers["jang_4m__osaurus"]["answers"] = [
            item for item in answers["jang_4m__osaurus"]["answers"]
            if item["prompt_id"] != "tradeoff-explain"
        ]
        with TemporaryDirectory() as tmp:
            with self.assertRaises(PreferenceError) as ctx:
                write_review(
                    Path(tmp),
                    pairs,
                    answers,
                    _prompts_by_id(),
                )
            message = str(ctx.exception)
            self.assertIn("tradeoff-explain", message)
            self.assertIn("jang_4m__osaurus", message)


if __name__ == "__main__":
    unittest.main()
