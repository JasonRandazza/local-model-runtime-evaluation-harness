"""Load and validate Gemma preference suite config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PREFERENCE_CELLS: tuple[str, ...] = (
    "jang_4m__osaurus",
    "oq4_fp16__omlx",
    "optiq_4bit__optiq",
)

SUITE_FIELDS = frozenset({
    "schema_version", "suite_id", "revision", "temperature", "streaming", "prompts",
})

PROMPT_FIELDS = frozenset({"prompt_id", "prompt", "max_tokens"})


class PreferenceError(RuntimeError):
    pass


def _require_exact_fields(data: dict[str, Any], expected: frozenset[str], label: str) -> None:
    if set(data) != expected:
        raise PreferenceError(f"{label} fields are invalid")


@dataclass(frozen=True)
class PreferencePrompt:
    prompt_id: str
    prompt: str
    max_tokens: int


@dataclass(frozen=True)
class PreferenceSuite:
    suite_id: str
    revision: str
    prompts: tuple[PreferencePrompt, ...]

    @classmethod
    def load(cls, path: Path) -> PreferenceSuite:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise PreferenceError("suite must be a JSON object")
        _require_exact_fields(data, SUITE_FIELDS, "suite")
        if data["schema_version"] != "1.0.0":
            raise PreferenceError("suite schema_version is invalid")
        if data["temperature"] != 0 or data["streaming"] is not True:
            raise PreferenceError("suite must be deterministic and streaming")
        items = data["prompts"]
        if not isinstance(items, list) or len(items) != 6:
            raise PreferenceError("suite must contain exactly six prompts")
        prompts: list[PreferencePrompt] = []
        for item in items:
            if not isinstance(item, dict):
                raise PreferenceError("prompt fields are invalid")
            _require_exact_fields(item, PROMPT_FIELDS, "prompt")
            max_tokens = item["max_tokens"]
            if not isinstance(max_tokens, int) or max_tokens <= 0:
                raise PreferenceError("prompt max_tokens must be a positive integer")
            prompts.append(
                PreferencePrompt(
                    str(item["prompt_id"]),
                    str(item["prompt"]),
                    max_tokens,
                )
            )
        if len({prompt.prompt_id for prompt in prompts}) != 6:
            raise PreferenceError("prompt IDs must be unique")
        return cls(str(data["suite_id"]), str(data["revision"]), tuple(prompts))
