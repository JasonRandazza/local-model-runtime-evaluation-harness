"""Score RAG oracle answers by required-fact hit rate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .rag_config import RagError, RagSuite

AnswerScore = dict[str, int | float | list[str]]


def score_answer(
    content: str | None,
    required_facts: tuple[str, ...],
    *,
    success: bool,
) -> AnswerScore:
    total = len(required_facts)
    if not success or content is None:
        return {
            "hits": 0,
            "total": total,
            "hit_rate": 0.0,
            "missing_facts": list(required_facts),
        }
    missing = [fact for fact in required_facts if fact not in content]
    hits = total - len(missing)
    return {
        "hits": hits,
        "total": total,
        "hit_rate": (hits / total) if total else 0.0,
        "missing_facts": missing,
    }


def _format_hit_rate(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _questions_by_id(suite: RagSuite) -> dict[str, tuple[str, ...]]:
    return {question.prompt_id: question.required_facts for question in suite.questions}


def _load_answer_files(run_dir: Path) -> dict[str, dict[str, Any]]:
    answers_dir = run_dir / "answers"
    if not answers_dir.is_dir():
        raise RagError(f"missing answers directory: {answers_dir}")
    cells: dict[str, dict[str, Any]] = {}
    for path in sorted(answers_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RagError(f"answers file must be a JSON object: {path}")
        cell_id = payload.get("cell_id")
        answers = payload.get("answers")
        if not isinstance(cell_id, str) or not cell_id:
            raise RagError(f"answers file cell_id is invalid: {path}")
        if not isinstance(answers, list):
            raise RagError(f"answers file must contain an answers array: {path}")
        cells[cell_id] = payload
    if not cells:
        raise RagError(f"no answer files found under {answers_dir}")
    return cells


def _score_cell(
    answers: list[dict[str, Any]],
    required_by_prompt: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    prompts: dict[str, AnswerScore] = {}
    for entry in answers:
        if not isinstance(entry, dict):
            raise RagError("answer entries must be objects")
        prompt_id = entry.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise RagError("answer prompt_id must be a non-empty string")
        required_facts = required_by_prompt.get(prompt_id)
        if required_facts is None:
            raise RagError(f"unknown prompt_id in answers: {prompt_id}")
        content = entry.get("content")
        success = entry.get("success")
        if not isinstance(success, bool):
            raise RagError(f"answer success must be boolean for prompt {prompt_id!r}")
        if content is not None and not isinstance(content, str):
            raise RagError(f"answer content must be a string or null for prompt {prompt_id!r}")
        prompts[prompt_id] = score_answer(content, required_facts, success=success)

    hit_rates = [float(score["hit_rate"]) for score in prompts.values()]
    mean_hit_rate = (sum(hit_rates) / len(hit_rates)) if hit_rates else 0.0
    return {
        "mean_hit_rate": mean_hit_rate,
        "prompts": prompts,
    }


def render_score_report(
    cells: dict[str, dict[str, Any]],
    *,
    run_id: str,
    suite_id: str,
) -> str:
    ranked = sorted(
        cells.items(),
        key=lambda item: float(item[1]["mean_hit_rate"]),
        reverse=True,
    )
    lines = [
        "# RAG oracle score",
        "",
        f"Run: `{run_id}`",
        f"Suite: `{suite_id}`",
        "",
        "| Rank | Cell | Mean hit rate |",
        "| ---: | --- | ---: |",
    ]
    for rank, (cell_id, cell_stats) in enumerate(ranked, start=1):
        lines.append(
            f"| {rank} | {cell_id} | "
            f"{_format_hit_rate(float(cell_stats['mean_hit_rate']))} |"
        )
    lines.extend([
        "",
        "Per-prompt scores are recorded in `scores.json`.",
        "Latency was not used for RAG scoring.",
        "",
    ])
    return "\n".join(lines)


def score_run(run_dir: Path, suite: RagSuite) -> Path:
    required_by_prompt = _questions_by_id(suite)
    answer_files = _load_answer_files(run_dir)
    cells: dict[str, dict[str, Any]] = {}
    for cell_id, payload in answer_files.items():
        answers = payload["answers"]
        if not isinstance(answers, list):
            raise RagError(f"answers file must contain an answers array for cell {cell_id!r}")
        cells[cell_id] = _score_cell(answers, required_by_prompt)

    scores_payload = {
        "run_id": run_dir.name,
        "suite_id": suite.suite_id,
        "cells": cells,
    }
    (run_dir / "scores.json").write_text(
        json.dumps(scores_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = render_score_report(
        cells,
        run_id=run_dir.name,
        suite_id=suite.suite_id,
    )
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    return run_dir
