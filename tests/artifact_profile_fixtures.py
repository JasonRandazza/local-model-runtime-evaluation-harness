from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from local_model_runtime_evaluation.artifact_profile import ArtifactRoots


def synthetic_artifact_roots() -> ArtifactRoots:
    return ArtifactRoots(
        huggingface_hub=Path("/synthetic/huggingface-hub"),
        local_models=Path("/synthetic/local-models"),
    )


def write_machine_profile(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    roots = {
        "huggingface_hub": root / "huggingface-hub",
        "local_models": root / "local-models",
    }
    for path in roots.values():
        path.mkdir(exist_ok=True)
    profile = root / "machine-profile.json"
    profile.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "artifact_roots": {
                    key: str(value) for key, value in roots.items()
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return profile


@contextmanager
def temporary_machine_profile() -> Iterator[tuple[Path, dict[str, Path]]]:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = write_machine_profile(root)
        payload = json.loads(profile.read_text(encoding="utf-8"))
        roots = {
            key: Path(value)
            for key, value in payload["artifact_roots"].items()
        }
        yield profile, roots
