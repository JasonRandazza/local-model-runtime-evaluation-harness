"""Persist and enumerate rulings on disk, one ruling per file.

`save_ruling` writes a single ruling as JSON to `rulings_root / {ruling_id}.json`
and never overwrites an existing file; `list_rulings` reads every ruling back and
derives which ones have been superseded by a later conclusion under the same run.

Neither function touches configuration, a network endpoint, a model, or any
runtime: both take their directory as an argument so they stay import-safe and
testable in isolation. Superseding is derived at read time, never stored -- the
earlier ruling recorded an honest conclusion under its own rubric and evidence;
`list_rulings` only points later entries back at it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# The three keys a saved ruling must carry, each a non-empty string. A ruling
# missing any of them -- or carrying an empty one -- is UNAVAILABLE and must not
# be persisted.
_REQUIRED_KEYS = frozenset({"ruling_id", "created_at", "run_id"})


class RulingStoreError(RuntimeError):
    pass


def _is_valid_ruling(ruling: object) -> bool:
    if not isinstance(ruling, dict):
        return False
    for key in _REQUIRED_KEYS:
        value = ruling.get(key)
        if not isinstance(value, str) or value == "":
            return False
    return True


def save_ruling(rulings_root: Path, ruling: dict) -> Path:
    """Write one ruling as JSON to `rulings_root / {ruling_id}.json`.

    Raises RulingStoreError for an UNAVAILABLE ruling (not a dict, or missing an
    identity key), for a ruling id that would escape its directory, or if the
    target already exists. Writes atomically via a sibling ``*.tmp`` file and
    `os.replace`, so a crash mid-write never leaves a half-read ruling.
    """

    if not isinstance(ruling, dict):
        raise RulingStoreError("ruling is not an object")

    for key in _REQUIRED_KEYS:
        value = ruling.get(key)
        if not isinstance(value, str) or value == "":
            raise RulingStoreError(f"ruling is missing a non-empty {key!r}")

    ruling_id = ruling["ruling_id"]
    if "/" in ruling_id or "\\" in ruling_id or ".." in ruling_id:
        raise RulingStoreError("ruling_id escapes its directory")
    if Path(ruling_id).name != ruling_id:
        raise RulingStoreError("ruling_id is not a bare file name")

    target = rulings_root / f"{ruling_id}.json"
    if target.exists():
        raise RulingStoreError(f"a ruling already exists at {target}")

    rulings_root.mkdir(parents=True, exist_ok=True)
    tmp_path = target.parent / (target.name + ".tmp")
    text = json.dumps(ruling, indent=2, sort_keys=True) + "\n"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, target)
    return target


def list_rulings(rulings_root: Path) -> list[dict]:
    """Read every ruling directly inside `rulings_root` and report its status.

    Never raises. A missing or unreadable directory yields an empty list; a file
    that is a symlink, is not valid JSON, is not an object, or lacks the three
    required string keys is skipped silently so junk never breaks listing the
    good ones. Entries are grouped by `run_id` and any ruling beaten to a later
    conclusion under the same run gets `superseded_by` set to that current
    ruling's id; ties on `created_at` break toward the greater `ruling_id`. The
    result is ordered newest first.
    """

    entries = []
    try:
        for raw_path in sorted(rulings_root.glob("*.json")):
            if raw_path.is_symlink():
                continue
            try:
                ruling = json.loads(raw_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not _is_valid_ruling(ruling):
                continue
            entries.append((raw_path, ruling))
    except OSError:
        return []

    groups: dict[str, list[tuple[Path, dict]]] = {}
    for raw_path, ruling in entries:
        groups.setdefault(ruling["run_id"], []).append((raw_path, ruling))

    result: list[dict] = []
    for group in groups.values():
        current_index = max(
            range(len(group)),
            key=lambda i: (group[i][1]["created_at"], group[i][1]["ruling_id"]),
        )
        current_ruling_id = group[current_index][1]["ruling_id"]
        for index, (raw_path, ruling) in enumerate(group):
            result.append({
                "ruling_id": ruling["ruling_id"],
                "created_at": ruling["created_at"],
                "run_id": ruling["run_id"],
                "path": str(raw_path),
                "superseded_by": None if index == current_index else current_ruling_id,
                "ruling": ruling,
            })

    result.sort(key=lambda entry: (entry["created_at"], entry["ruling_id"]), reverse=True)
    return result
