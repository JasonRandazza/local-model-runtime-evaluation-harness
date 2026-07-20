"""Score RAG oracle and keyword answers by fact-hit and retrieval metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .rag_config import RagError, RagSuite

AnswerScore = dict[str, int | float | list[str] | dict[str, int | float]]
RetrievalScore = dict[str, int | float]


def score_retrieval(
    retrieved: tuple[str, ...] | list[str],
    gold: tuple[str, ...],
) -> RetrievalScore:
    retrieved_list = list(retrieved)
    gold_set = set(gold)
    retrieved_set = set(retrieved_list)
    hits = len(retrieved_set & gold_set)
    gold_total = len(gold_set)
    retrieved_total = len(retrieved_list)
    recall = (hits / gold_total) if gold_total else 0.0
    precision = (hits / retrieved_total) if retrieved_total else 0.0
    return {
        "hits": hits,
        "gold_total": gold_total,
        "retrieved_total": retrieved_total,
        "recall": recall,
        "precision": precision,
    }


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


def _format_rate(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _questions_by_id(suite: RagSuite) -> dict[str, tuple[str, ...]]:
    return {question.prompt_id: question.required_facts for question in suite.questions}


def _gold_by_prompt_id(suite: RagSuite) -> dict[str, tuple[str, ...]]:
    return {question.prompt_id: question.gold_chunk_ids for question in suite.questions}


def _load_run_metadata(run_dir: Path) -> tuple[str, int | None]:
    raw_path = run_dir / "raw.json"
    if not raw_path.is_file():
        return "oracle", None
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RagError(f"raw.json must be a JSON object: {raw_path}")
    mode = payload.get("mode", "oracle")
    if not isinstance(mode, str):
        raise RagError(f"raw.json mode must be a string: {raw_path}")
    if mode not in {"oracle", "keyword"}:
        raise RagError(f"unknown raw.json mode {mode!r}: {raw_path}")
    top_k = payload.get("top_k")
    if top_k is not None and not isinstance(top_k, int):
        raise RagError(f"raw.json top_k must be an integer: {raw_path}")
    return mode, top_k


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


def _parse_retrieved_ids(entry: dict[str, Any], prompt_id: str) -> tuple[str, ...]:
    retrieved = entry.get("retrieved_chunk_ids")
    if retrieved is None:
        raise RagError(
            f"keyword answer missing retrieved_chunk_ids for prompt {prompt_id!r}"
        )
    if not isinstance(retrieved, list) or not all(isinstance(item, str) for item in retrieved):
        raise RagError(
            f"retrieved_chunk_ids must be a string list for prompt {prompt_id!r}"
        )
    return tuple(retrieved)


def _score_cell(
    answers: list[dict[str, Any]],
    required_by_prompt: dict[str, tuple[str, ...]],
    *,
    mode: str,
    gold_by_prompt: dict[str, tuple[str, ...]] | None = None,
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
        prompt_score = score_answer(content, required_facts, success=success)
        if mode == "keyword":
            if gold_by_prompt is None:
                raise RagError("gold chunk ids required for keyword scoring")
            gold = gold_by_prompt.get(prompt_id)
            if gold is None:
                raise RagError(f"unknown prompt_id in suite: {prompt_id}")
            retrieved = _parse_retrieved_ids(entry, prompt_id)
            prompt_score["retrieval"] = score_retrieval(retrieved, gold)
        prompts[prompt_id] = prompt_score

    hit_rates = [float(score["hit_rate"]) for score in prompts.values()]
    mean_hit_rate = (sum(hit_rates) / len(hit_rates)) if hit_rates else 0.0
    result: dict[str, Any] = {
        "mean_hit_rate": mean_hit_rate,
        "prompts": prompts,
    }
    if mode == "keyword":
        recalls = [
            float(score["retrieval"]["recall"])  # type: ignore[index]
            for score in prompts.values()
        ]
        precisions = [
            float(score["retrieval"]["precision"])  # type: ignore[index]
            for score in prompts.values()
        ]
        result["mean_recall"] = (sum(recalls) / len(recalls)) if recalls else 0.0
        result["mean_precision"] = (
            (sum(precisions) / len(precisions)) if precisions else 0.0
        )
    return result


def render_score_report(
    cells: dict[str, dict[str, Any]],
    *,
    run_id: str,
    suite_id: str,
    mode: str = "oracle",
    top_k: int | None = None,
) -> str:
    ranked_hit = sorted(
        cells.items(),
        key=lambda item: float(item[1]["mean_hit_rate"]),
        reverse=True,
    )
    title = "RAG keyword score" if mode == "keyword" else "RAG oracle score"
    lines = [
        f"# {title}",
        "",
        f"Run: `{run_id}`",
        f"Suite: `{suite_id}`",
        f"Mode: `{mode}`",
    ]
    if mode == "keyword" and top_k is not None:
        lines.append(f"Top-k: `{top_k}`")
    lines.extend(["", ""])

    if mode == "keyword":
        ranked_recall = sorted(
            cells.items(),
            key=lambda item: float(item[1]["mean_recall"]),
            reverse=True,
        )
        lines.extend([
            "## Retrieval (mean recall@k)",
            "",
            "| Rank | Cell | Mean recall | Mean precision |",
            "| ---: | --- | ---: | ---: |",
        ])
        for rank, (cell_id, cell_stats) in enumerate(ranked_recall, start=1):
            lines.append(
                f"| {rank} | {cell_id} | "
                f"{_format_rate(float(cell_stats['mean_recall']))} | "
                f"{_format_rate(float(cell_stats['mean_precision']))} |"
            )
        lines.extend(["", ""])

    lines.extend([
        "## Generation (mean fact-hit rate)",
        "",
        "| Rank | Cell | Mean hit rate |",
        "| ---: | --- | ---: |",
    ])
    for rank, (cell_id, cell_stats) in enumerate(ranked_hit, start=1):
        lines.append(
            f"| {rank} | {cell_id} | "
            f"{_format_rate(float(cell_stats['mean_hit_rate']))} |"
        )
    lines.extend([
        "",
        "Per-prompt scores are recorded in `scores.json`.",
        "Latency was not used for RAG scoring.",
        "",
    ])
    return "\n".join(lines)


def score_run(run_dir: Path, suite: RagSuite) -> Path:
    mode, top_k = _load_run_metadata(run_dir)
    required_by_prompt = _questions_by_id(suite)
    gold_by_prompt = _gold_by_prompt_id(suite) if mode == "keyword" else None
    answer_files = _load_answer_files(run_dir)
    cells: dict[str, dict[str, Any]] = {}
    for cell_id, payload in answer_files.items():
        answers = payload["answers"]
        if not isinstance(answers, list):
            raise RagError(f"answers file must contain an answers array for cell {cell_id!r}")
        cells[cell_id] = _score_cell(
            answers,
            required_by_prompt,
            mode=mode,
            gold_by_prompt=gold_by_prompt,
        )

    scores_payload: dict[str, Any] = {
        "run_id": run_dir.name,
        "suite_id": suite.suite_id,
        "mode": mode,
        "cells": cells,
    }
    if mode == "keyword":
        scores_payload["top_k"] = top_k if top_k is not None else 2
    (run_dir / "scores.json").write_text(
        json.dumps(scores_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = render_score_report(
        cells,
        run_id=run_dir.name,
        suite_id=suite.suite_id,
        mode=mode,
        top_k=scores_payload.get("top_k"),
    )
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    return run_dir
