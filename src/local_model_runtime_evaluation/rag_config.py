"""Load and validate Gemma RAG oracle corpus and suite config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .matrix_config import REPOSITORY_ROOT


DEFAULT_RAG_ROOT = REPOSITORY_ROOT / "config" / "rag"
DEFAULT_RAG_DEFAULTS = DEFAULT_RAG_ROOT / "defaults.json"
DEFAULT_FAMILY_CELLS = DEFAULT_RAG_ROOT / "family-cells.json"

SUITE_FIELDS = frozenset({
    "schema_version", "suite_id", "revision", "temperature", "streaming", "corpus_id", "questions",
})

QUESTION_FIELDS = frozenset({
    "prompt_id", "question", "gold_chunk_ids", "required_facts", "max_tokens",
})

MANIFEST_FIELDS = frozenset({"corpus_id", "chunks"})
CHUNK_ENTRY_FIELDS = frozenset({"chunk_id", "path", "title"})


class RagError(RuntimeError):
    pass


@dataclass(frozen=True)
class RagDefaults:
    family_id: str
    cells: tuple[str, ...]


@dataclass(frozen=True)
class RagSelection:
    family_id: str
    cells: tuple[str, ...]


def load_rag_defaults(path: Path | None = None) -> RagDefaults:
    config_path = DEFAULT_RAG_DEFAULTS if path is None else path
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RagError("rag defaults must be a JSON object")
    family_id = data.get("family_id")
    cells = data.get("cells")
    if not isinstance(family_id, str):
        raise RagError("rag defaults family_id is invalid")
    if not isinstance(cells, list) or not all(isinstance(cell, str) for cell in cells):
        raise RagError("rag defaults cells are invalid")
    return RagDefaults(family_id, tuple(cells))


def load_rag_family_cell_recipes(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    config_path = DEFAULT_FAMILY_CELLS if path is None else path
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RagError("rag family cell recipes must be a JSON object")
    recipes: dict[str, tuple[str, ...]] = {}
    for family_id, cells in data.items():
        if not isinstance(family_id, str):
            raise RagError("rag family cell recipe key is invalid")
        if not isinstance(cells, list) or not all(isinstance(cell, str) for cell in cells):
            raise RagError(f"rag family cell recipe for {family_id!r} is invalid")
        recipes[family_id] = tuple(cells)
    return recipes


def default_rag_cells() -> tuple[str, ...]:
    return load_rag_defaults().cells


DEFAULT_RAG_CELLS = default_rag_cells()


def resolve_rag_selection(
    *,
    family_id: str | None,
    cells: tuple[str, ...] | None,
    defaults: RagDefaults | None = None,
    recipes: dict[str, tuple[str, ...]] | None = None,
) -> RagSelection:
    resolved_defaults = load_rag_defaults() if defaults is None else defaults
    resolved_recipes = load_rag_family_cell_recipes() if recipes is None else recipes

    resolved_family = family_id if family_id else resolved_defaults.family_id
    if not resolved_family:
        raise RagError("family is required")

    if resolved_family not in resolved_recipes:
        raise RagError("rag family recipe is missing")

    resolved_cells = cells if cells is not None else resolved_recipes[resolved_family]
    if not resolved_cells:
        raise RagError("cells filter is empty")

    return RagSelection(resolved_family, resolved_cells)


def _require_exact_fields(data: dict[str, Any], expected: frozenset[str], label: str) -> None:
    if set(data) != expected:
        raise RagError(f"{label} fields are invalid")


@dataclass(frozen=True)
class CorpusChunk:
    chunk_id: str
    title: str
    text: str


@dataclass(frozen=True)
class RagCorpus:
    corpus_id: str
    chunks: tuple[CorpusChunk, ...]

    def get(self, chunk_id: str) -> CorpusChunk:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        raise RagError(f"unknown chunk id: {chunk_id}")

    @classmethod
    def load(cls, root: Path) -> RagCorpus:
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise RagError("corpus manifest is missing")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RagError("corpus manifest must be a JSON object")
        _require_exact_fields(data, MANIFEST_FIELDS, "corpus manifest")
        corpus_id = str(data["corpus_id"])
        entries = data["chunks"]
        if not isinstance(entries, list) or len(entries) == 0:
            raise RagError("corpus manifest chunks are invalid")
        chunks: list[CorpusChunk] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise RagError("corpus chunk entry is invalid")
            _require_exact_fields(entry, CHUNK_ENTRY_FIELDS, "corpus chunk entry")
            chunk_id = str(entry["chunk_id"])
            rel_path = str(entry["path"])
            title = str(entry["title"])
            chunk_path = root / rel_path
            if not chunk_path.is_file():
                raise RagError(f"corpus chunk file is missing: {rel_path}")
            chunks.append(
                CorpusChunk(chunk_id, title, chunk_path.read_text(encoding="utf-8"))
            )
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise RagError("corpus chunk ids must be unique")
        return cls(corpus_id, tuple(chunks))


@dataclass(frozen=True)
class RagQuestion:
    prompt_id: str
    question: str
    gold_chunk_ids: tuple[str, ...]
    required_facts: tuple[str, ...]
    max_tokens: int


@dataclass(frozen=True)
class RagSuite:
    suite_id: str
    revision: str
    corpus_id: str
    questions: tuple[RagQuestion, ...]

    @classmethod
    def load(cls, path: Path) -> RagSuite:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RagError("suite must be a JSON object")
        _require_exact_fields(data, SUITE_FIELDS, "suite")
        if data["schema_version"] != "1.0.0":
            raise RagError("suite schema_version is invalid")
        if data["temperature"] != 0 or data["streaming"] is not True:
            raise RagError("suite must be deterministic and streaming")
        if data["corpus_id"] != "rag-oracle-v1":
            raise RagError("suite corpus_id is invalid")
        items = data["questions"]
        if not isinstance(items, list) or len(items) != 6:
            raise RagError("suite must contain exactly six questions")
        questions: list[RagQuestion] = []
        for item in items:
            if not isinstance(item, dict):
                raise RagError("question fields are invalid")
            _require_exact_fields(item, QUESTION_FIELDS, "question")
            gold_chunk_ids = item["gold_chunk_ids"]
            required_facts = item["required_facts"]
            if not isinstance(gold_chunk_ids, list) or len(gold_chunk_ids) == 0:
                raise RagError("question gold_chunk_ids must be a non-empty list")
            if not isinstance(required_facts, list) or len(required_facts) == 0:
                raise RagError("question required_facts must be a non-empty list")
            max_tokens = item["max_tokens"]
            if not isinstance(max_tokens, int) or max_tokens <= 0:
                raise RagError("question max_tokens must be a positive integer")
            questions.append(
                RagQuestion(
                    str(item["prompt_id"]),
                    str(item["question"]),
                    tuple(str(chunk_id) for chunk_id in gold_chunk_ids),
                    tuple(str(fact) for fact in required_facts),
                    max_tokens,
                )
            )
        if len({question.prompt_id for question in questions}) != 6:
            raise RagError("question prompt IDs must be unique")
        return cls(
            str(data["suite_id"]),
            str(data["revision"]),
            str(data["corpus_id"]),
            tuple(questions),
        )
