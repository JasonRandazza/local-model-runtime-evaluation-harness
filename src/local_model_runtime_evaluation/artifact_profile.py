"""Strict local machine-profile loading for portable model artifact roots."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .workspace import workspace_root
from typing import Any


PROFILE_SCHEMA_VERSION = "1.0.0"
PROFILE_FIELDS = frozenset({"schema_version", "artifact_roots"})
ARTIFACT_ROOT_KEYS = frozenset({"huggingface_hub", "local_models"})
ARTIFACT_PATH_TOKEN = "{artifact_path}"
OMLX_CATALOG_TOKEN = "{LMRE_OMLX_CATALOG}"
ALLOWED_PASSTHROUGH_TOKENS = frozenset({OMLX_CATALOG_TOKEN})
_ROOT_TEMPLATE = re.compile(r"\{LMRE_ROOT:([a-z_]+)\}/(.+)")
# Resolved workspace root. Kept under the historical name so the modules
# that derive path constants from it need no change; a checkout resolves
# to the repository root exactly as before.
REPOSITORY_ROOT = workspace_root()
DEFAULT_MACHINE_PROFILE_PATH = REPOSITORY_ROOT / ".lmre" / "machine-profile.json"


class ArtifactProfileError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactRoots:
    huggingface_hub: Path
    local_models: Path

    def for_key(self, key: str) -> Path:
        if key not in ARTIFACT_ROOT_KEYS:
            raise ArtifactProfileError("artifact root key is invalid")
        return getattr(self, key)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactProfileError("machine profile is unreadable") from error
    if not isinstance(body, dict):
        raise ArtifactProfileError("machine profile must be a JSON object")
    return body


def _root_directory(value: object, key: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ArtifactProfileError(f"artifact root {key!r} is invalid")
    path = Path(value)
    if not path.is_absolute() or value != str(path) or ".." in path.parts:
        raise ArtifactProfileError(f"artifact root {key!r} must be normalized and absolute")
    if not path.is_dir():
        raise ArtifactProfileError(f"artifact root {key!r} must be an existing directory")
    return path.resolve()


def load_artifact_roots(path: Path) -> ArtifactRoots:
    body = _load_json_object(path)
    if set(body) != PROFILE_FIELDS:
        raise ArtifactProfileError("machine profile fields are invalid")
    if body["schema_version"] != PROFILE_SCHEMA_VERSION:
        raise ArtifactProfileError("machine profile schema_version is invalid")
    raw_roots = body["artifact_roots"]
    if not isinstance(raw_roots, dict) or set(raw_roots) != ARTIFACT_ROOT_KEYS:
        raise ArtifactProfileError("machine profile artifact_roots are invalid")
    return ArtifactRoots(
        huggingface_hub=_root_directory(
            raw_roots["huggingface_hub"], "huggingface_hub"
        ),
        local_models=_root_directory(raw_roots["local_models"], "local_models"),
    )


def resolve_artifact_template(template: str, roots: ArtifactRoots) -> str:
    if not isinstance(template, str):
        raise ArtifactProfileError("artifact template must be a string")
    match = _ROOT_TEMPLATE.fullmatch(template)
    if match is None:
        raise ArtifactProfileError("artifact template is invalid")
    key, suffix = match.groups()
    if key not in ARTIFACT_ROOT_KEYS:
        raise ArtifactProfileError("artifact template root is invalid")
    if "\\" in suffix or "{" in suffix or "}" in suffix:
        raise ArtifactProfileError("artifact template suffix is invalid")
    raw_parts = suffix.split("/")
    relative = PurePosixPath(suffix)
    if (
        not suffix
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise ArtifactProfileError("artifact template suffix is invalid")
    root = roots.for_key(key).resolve()
    resolved = (root / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(root):
        raise ArtifactProfileError("artifact template escapes configured root")
    return str(resolved)


def resolve_artifact_text(
    value: str,
    artifact_path: str,
    *,
    allowed_tokens: frozenset[str] = frozenset(),
) -> str:
    if not isinstance(value, str):
        raise ArtifactProfileError("artifact-bound value must be a string")
    path = Path(artifact_path)
    if not path.is_absolute() or artifact_path != str(path):
        raise ArtifactProfileError("resolved artifact path must be normalized and absolute")
    if not allowed_tokens.issubset(ALLOWED_PASSTHROUGH_TOKENS):
        raise ArtifactProfileError("artifact-bound token allowlist is invalid")
    resolved = value.replace(ARTIFACT_PATH_TOKEN, artifact_path)
    remainder = resolved
    for token in allowed_tokens:
        remainder = remainder.replace(token, "")
    if "{" in remainder or "}" in remainder:
        raise ArtifactProfileError("artifact-bound value contains an invalid token")
    return resolved
