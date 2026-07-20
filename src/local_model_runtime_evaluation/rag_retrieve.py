"""Term-overlap retrieval for Gemma RAG keyword mode."""

from __future__ import annotations

import re

from .rag_config import RagCorpus, RagError

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(text.lower()))


def score_chunk(query_tokens: tuple[str, ...], chunk_text: str) -> int:
    chunk_tokens = set(tokenize(chunk_text))
    return sum(1 for token in query_tokens if token in chunk_tokens)


def retrieve_top_k(query: str, corpus: RagCorpus, *, k: int) -> tuple[str, ...]:
    if k < 1:
        raise RagError("k must be at least 1")
    query_tokens = tokenize(query)
    ranked = sorted(
        corpus.chunks,
        key=lambda chunk: (-score_chunk(query_tokens, chunk.text), chunk.chunk_id),
    )
    return tuple(chunk.chunk_id for chunk in ranked[:k])
