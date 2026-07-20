"""Build oracle-injected and keyword-retrieved RAG prompts."""

from __future__ import annotations

from .rag_config import RagCorpus, RagQuestion
from .rag_retrieve import retrieve_top_k

_INSTRUCTION = (
    "Use only the provided context to answer the question. "
    "Do not use outside knowledge."
)


def build_context_prompt(
    chunk_ids: tuple[str, ...],
    question: RagQuestion,
    corpus: RagCorpus,
) -> str:
    parts = [_INSTRUCTION, ""]
    for chunk_id in chunk_ids:
        chunk = corpus.get(chunk_id)
        parts.extend([
            f"## Context: {chunk_id}",
            "",
            chunk.text.strip(),
            "",
        ])
    parts.extend([
        "Question:",
        question.question,
    ])
    return "\n".join(parts)


def build_oracle_prompt(question: RagQuestion, corpus: RagCorpus) -> str:
    return build_context_prompt(question.gold_chunk_ids, question, corpus)


def build_keyword_prompt(
    question: RagQuestion,
    corpus: RagCorpus,
    *,
    k: int,
) -> tuple[str, tuple[str, ...]]:
    retrieved_ids = retrieve_top_k(question.question, corpus, k=k)
    prompt = build_context_prompt(retrieved_ids, question, corpus)
    return prompt, retrieved_ids
