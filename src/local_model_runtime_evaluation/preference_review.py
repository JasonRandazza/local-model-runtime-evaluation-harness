"""Build blind pairwise review packs from collected preference answers."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from random import Random
from typing import Any

from .preference_config import PreferenceError, PreferenceSuite


def _unordered_cell_pairs(cell_ids: tuple[str, ...]) -> list[tuple[str, str]]:
    return list(combinations(sorted(cell_ids), 2))


def build_pairs(
    cell_ids: tuple[str, ...],
    prompt_ids: tuple[str, ...],
    *,
    rng: Random,
) -> list[dict[str, str]]:
    pairs_cells = _unordered_cell_pairs(cell_ids)
    pairs: list[dict[str, str]] = []
    for prompt_id in prompt_ids:
        for index, (left, right) in enumerate(pairs_cells):
            cell_a, cell_b = (left, right) if rng.random() < 0.5 else (right, left)
            pairs.append({
                "pair_id": f"{prompt_id}__{index:02d}",
                "prompt_id": prompt_id,
                "cell_a": cell_a,
                "cell_b": cell_b,
            })
    return pairs


def get_answer_content(
    answers_by_cell: dict[str, dict[str, Any]],
    cell_id: str,
    prompt_id: str,
) -> str:
    payload = answers_by_cell.get(cell_id)
    if payload is None:
        raise PreferenceError(f"missing answers for cell {cell_id!r}")
    answers = payload.get("answers")
    if not isinstance(answers, list):
        raise PreferenceError(f"missing answers for cell {cell_id!r}")
    for item in answers:
        if not isinstance(item, dict):
            continue
        if item.get("prompt_id") != prompt_id:
            continue
        content = item.get("content")
        if isinstance(content, str) and content:
            return content
        raise PreferenceError(
            f"missing answer content for prompt {prompt_id!r} cell {cell_id!r}"
        )
    raise PreferenceError(
        f"missing answer content for prompt {prompt_id!r} cell {cell_id!r}"
    )


def _render_review_markdown(
    pairs: list[dict[str, str]],
    answers_by_cell: dict[str, dict[str, Any]],
    prompts_by_id: dict[str, str],
) -> str:
    lines = [
        "# Preference review",
        "",
        "Do not look up cell ids; mark judgments.json only.",
        "",
    ]
    for pair in pairs:
        prompt_id = pair["prompt_id"]
        prompt_text = prompts_by_id[prompt_id]
        answer_a = get_answer_content(answers_by_cell, pair["cell_a"], prompt_id)
        answer_b = get_answer_content(answers_by_cell, pair["cell_b"], prompt_id)
        lines.extend([
            f"### Pair `{pair['pair_id']}`",
            f"Prompt (`{prompt_id}`):",
            "",
            f"> {prompt_text}",
            "",
            "**A**",
            "",
            answer_a,
            "",
            "**B**",
            "",
            answer_b,
            "",
            "Winner: _(set in judgments.json: A | B | tie)_",
            "",
        ])
    return "\n".join(lines)


def write_review(
    run_dir: Path,
    pairs: list[dict[str, str]],
    answers_by_cell: dict[str, dict[str, Any]],
    prompts_by_id: dict[str, str],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    review_md = _render_review_markdown(pairs, answers_by_cell, prompts_by_id)
    (run_dir / "review.md").write_text(review_md, encoding="utf-8")
    pairs_payload = {"pairs": pairs}
    (run_dir / "pairs.json").write_text(
        json.dumps(pairs_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    judgments_payload = {
        "judgments": [{"pair_id": pair["pair_id"], "winner": None} for pair in pairs],
    }
    (run_dir / "judgments.json").write_text(
        json.dumps(judgments_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_answers(run_dir: Path) -> dict[str, dict[str, Any]]:
    answers_dir = run_dir / "answers"
    if not answers_dir.is_dir():
        raise PreferenceError(f"missing answers directory: {answers_dir}")
    answers_by_cell: dict[str, dict[str, Any]] = {}
    for path in sorted(answers_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise PreferenceError(f"invalid answers file: {path}")
        cell_id = payload.get("cell_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise PreferenceError(f"invalid answers file: {path}")
        answers_by_cell[cell_id] = payload
    if not answers_by_cell:
        raise PreferenceError(f"no answer files found under {answers_dir}")
    return answers_by_cell


def run_review(
    run_dir: Path,
    *,
    seed: int,
    cell_ids: tuple[str, ...],
    suite: PreferenceSuite,
) -> None:
    answers_by_cell = load_answers(run_dir)
    missing_cells = [cell_id for cell_id in cell_ids if cell_id not in answers_by_cell]
    if missing_cells:
        raise PreferenceError(
            "missing answer files for cells: " + ", ".join(missing_cells)
        )
    prompt_ids = tuple(prompt.prompt_id for prompt in suite.prompts)
    prompts_by_id = {prompt.prompt_id: prompt.prompt for prompt in suite.prompts}
    pairs = build_pairs(cell_ids, prompt_ids, rng=Random(seed))
    write_review(run_dir, pairs, answers_by_cell, prompts_by_id)
