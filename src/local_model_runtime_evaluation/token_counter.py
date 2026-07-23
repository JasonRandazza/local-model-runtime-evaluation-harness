from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class FixedMapTokenCounter:
    """Test/helper counter: exact string → count; unknown strings → 0."""

    def __init__(self, counts: Mapping[str, int]) -> None:
        self._counts = dict(counts)

    def count(self, text: str) -> int:
        return int(self._counts.get(text, 0))


class ModelDirTokenCounter:
    """Best-effort HF tokenizer counter for a pinned model directory."""

    def __init__(self, model_dir: str | Path) -> None:
        self._model_dir = str(model_dir)
        self._tokenizer: object | None = None

    def _load(self) -> object:
        if self._tokenizer is not None:
            return self._tokenizer
        try:
            from transformers import AutoTokenizer  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError("transformers is not available") from error
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_dir,
            trust_remote_code=True,
        )
        return self._tokenizer

    def count(self, text: str) -> int:
        if not text:
            return 0
        tokenizer = self._load()
        encoded = tokenizer.encode(text, add_special_tokens=False)  # type: ignore[attr-defined]
        return len(encoded)


def try_model_dir_token_counter(model_dir: str | Path) -> TokenCounter | None:
    try:
        import transformers  # noqa: F401
    except ImportError:
        return None
    return ModelDirTokenCounter(model_dir)


def resolve_token_accounting(
    *,
    reasoning_text: str,
    visible_text: str,
    completion_tokens: int | None,
    usage_reasoning_tokens: int | None,
    token_counter: TokenCounter | None,
) -> tuple[int | None, int | None, str]:
    """Return (reasoning_tokens, visible_output_tokens, token_accounting_status)."""
    if usage_reasoning_tokens is not None:
        if completion_tokens is None:
            return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"
        if usage_reasoning_tokens > completion_tokens:
            return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"
        visible = completion_tokens - usage_reasoning_tokens
        if visible <= 0:
            return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"
        return usage_reasoning_tokens, visible, "EXACT_VISIBLE"

    if token_counter is None:
        return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"

    reasoning = token_counter.count(reasoning_text)
    visible = token_counter.count(visible_text)
    if reasoning < 0 or visible < 0:
        return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"

    if completion_tokens is not None:
        if reasoning + visible != completion_tokens:
            return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"
        if visible <= 0:
            return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"
        return reasoning, visible, "DERIVED_REASONING_CONTENT"

    if reasoning > 0 and visible > 0:
        return reasoning, visible, "DERIVED_REASONING_CONTENT"
    return None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"
