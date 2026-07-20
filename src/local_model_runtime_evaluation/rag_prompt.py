"""Build oracle-injected RAG prompts from gold corpus chunks."""

from __future__ import annotations

from .rag_config import RagCorpus, RagQuestion

_INSTRUCTION = (
    "Use only the provided context to answer the question. "
    "Do not use outside knowledge."
)


def build_oracle_prompt(question: RagQuestion, corpus: RagCorpus) -> str:
    parts = [_INSTRUCTION, ""]
    for chunk_id in question.gold_chunk_ids:
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
