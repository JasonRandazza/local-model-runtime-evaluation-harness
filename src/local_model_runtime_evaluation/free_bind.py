"""Offline declarations for reviewed, same-family managed cell bindings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .artifact_profile import (
    DEFAULT_MACHINE_PROFILE_PATH,
    ArtifactRoots,
    load_artifact_roots,
)
from .matrix_config import (
    DEFAULT_FAMILIES_ROOT,
    REPOSITORY_ROOT,
    Cell,
    MatrixError,
    ModelFamily,
)


BINDING_SCHEMA_VERSION = "1.0.0"
LIVE_STATUS_NOT_CHECKED = "NOT_CHECKED_LIVE"
STATUS_READY = "READY_FOR_ADOPTION"
STATUS_ACTION_REQUIRED = "ACTION_REQUIRED"
STATUS_STALE = "STALE_INPUTS"
SAFE_BINDING_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SAFE_CELL_ID = re.compile(r"[a-z0-9][a-z0-9_-]*__(?:osaurus|omlx|optiq)")
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
MAX_CELLS = 9

PROPOSAL_FIELDS = frozenset(
    {
        "schema_version",
        "binding_id",
        "revision",
        "family_id",
        "cell_ids",
        "notes",
        "require_native_server",
        "created_at",
        "source_hashes",
        "machine_profile_hash",
        "proposal_hash",
        "live_authority",
    }
)
ADOPTION_FIELDS = frozenset(
    {
        "schema_version",
        "adopted_at",
        "binding",
        "binding_hash",
        "proposal_hash",
        "live_authority",
    }
)
BINDING_FIELDS = frozenset(
    {
        "binding_id",
        "revision",
        "family_id",
        "cell_ids",
        "notes",
        "require_native_server",
        "source_hashes",
        "machine_profile_hash",
    }
)


class FreeBindError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "free_bind_invalid",
    ) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BindingSelection:
    binding_id: str
    revision: str
    family_id: str
    cell_ids: tuple[str, ...]
    notes: str


def _canonical_hash(body: object) -> str:
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise FreeBindError("binding input is unreadable") from error
    return digest.hexdigest()


def _utc_now(now: datetime | None) -> str:
    current = datetime.now(timezone.utc) if now is None else now
    if current.tzinfo is None or current.utcoffset() != timezone.utc.utcoffset(current):
        raise FreeBindError("binding time must use UTC")
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FreeBindError(f"{label} is invalid")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise FreeBindError(f"{label} is invalid") from error
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise FreeBindError(f"{label} is invalid")
    return value


def _hash_value(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256_HEX.fullmatch(value):
        raise FreeBindError(f"{label} is invalid")
    return value


def _source_hashes(value: object) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or not value
        or not all(
            isinstance(path, str)
            and path
            and not Path(path).is_absolute()
            and ".." not in Path(path).parts
            and isinstance(digest, str)
            and SHA256_HEX.fullmatch(digest)
            for path, digest in value.items()
        )
    ):
        raise FreeBindError("binding source_hashes are invalid")
    return value


def _safe_binding_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 80
        or not SAFE_BINDING_ID.fullmatch(value)
    ):
        raise FreeBindError("binding_id is invalid")
    return value


def _revision(value: object) -> str:
    if not isinstance(value, str) or not value.isdecimal() or int(value) < 1:
        raise FreeBindError("binding revision is invalid")
    return value


def _selection(
    binding_id: object,
    revision: object,
    family_id: object,
    cell_ids: object,
    notes: object,
) -> BindingSelection:
    resolved_id = _safe_binding_id(binding_id)
    if (
        not isinstance(family_id, str)
        or len(family_id) > 80
        or not SAFE_BINDING_ID.fullmatch(family_id)
    ):
        raise FreeBindError("family_id is invalid")
    if not isinstance(cell_ids, (list, tuple)) or not all(
        isinstance(item, str) and SAFE_CELL_ID.fullmatch(item) for item in cell_ids
    ):
        raise FreeBindError("cell_ids must contain safe checked-in cell IDs")
    resolved_cells = tuple(cell_ids)
    if len(resolved_cells) < 2:
        raise FreeBindError("a managed binding requires at least two cells")
    if len(resolved_cells) > MAX_CELLS:
        raise FreeBindError(f"a managed binding permits at most {MAX_CELLS} cells")
    if len(set(resolved_cells)) != len(resolved_cells):
        raise FreeBindError("cell_ids must be unique")
    if not isinstance(notes, str) or len(notes) > 1000:
        raise FreeBindError("binding notes are invalid")
    return BindingSelection(
        binding_id=resolved_id,
        revision=_revision(revision),
        family_id=family_id,
        cell_ids=resolved_cells,
        notes=notes,
    )


def _repo_relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as error:
        raise FreeBindError("binding input escaped the repository") from error


def _load_cells(
    selection: BindingSelection,
    *,
    repository_root: Path,
    families_root: Path,
    cells_root: Path,
) -> tuple[ModelFamily, tuple[Cell, ...], dict[str, str]]:
    family_path = families_root / f"{selection.family_id}.json"
    if not family_path.is_file() or family_path.is_symlink():
        raise FreeBindError("binding family is not a checked-in regular file")
    try:
        family = ModelFamily.load(family_path)
    except (MatrixError, OSError, ValueError, KeyError, TypeError) as error:
        raise FreeBindError("binding family is invalid") from error
    if family.family_id != selection.family_id:
        raise FreeBindError("binding family_id mismatch")

    cells: list[Cell] = []
    paths = [family_path]
    for cell_id in selection.cell_ids:
        cell_path = cells_root / f"{cell_id}.json"
        if not cell_path.is_file() or cell_path.is_symlink():
            raise FreeBindError(
                f"binding cell is not a checked-in regular file: {cell_id}",
                code="free_bind_cell_missing",
            )
        try:
            cell = Cell.load(
                cell_path,
                family=family,
                require_native_server=True,
            )
        except (MatrixError, OSError, ValueError, KeyError, TypeError) as error:
            raise FreeBindError(f"binding cell is invalid: {cell_id}") from error
        if cell.cell_id != cell_id:
            raise FreeBindError(f"binding cell identity mismatch: {cell_id}")
        cells.append(cell)
        paths.append(cell_path)
    hashes = {_repo_relative(path, repository_root): _sha256(path) for path in paths}
    return family, tuple(cells), dict(sorted(hashes.items()))


def _artifact_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    if not path.is_dir():
        return "WRONG_KIND"
    if not os.access(path, os.R_OK):
        return "UNREADABLE"
    return "PRESENT"


def _artifact_findings(
    cells: Sequence[Cell],
    roots: ArtifactRoots,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for cell in cells:
        try:
            resolved = cell.resolve(roots)
            artifact_path = Path(resolved.artifact_path)
            status = _artifact_status(artifact_path)
            path: str | None = str(artifact_path)
        except MatrixError:
            status = "INVALID_TEMPLATE"
            path = None
        findings.append(
            {
                "artifact_path": path,
                "cell_id": cell.cell_id,
                "server": cell.server,
                "status": status,
            }
        )
    return findings


def _binding_body(proposal: dict[str, object]) -> dict[str, object]:
    return {
        key: proposal[key]
        for key in (
            "binding_id",
            "revision",
            "family_id",
            "cell_ids",
            "notes",
            "require_native_server",
            "source_hashes",
            "machine_profile_hash",
        )
    }


def _proposal_body(proposal: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in proposal.items() if key != "proposal_hash"}


def _proposal_path(state_dir: Path, binding_id: str) -> Path:
    return state_dir / "bindings" / "proposals" / f"{binding_id}.json"


def _adopted_path(state_dir: Path, binding_id: str) -> Path:
    return state_dir / "bindings" / "adopted" / f"{binding_id}.json"


def _write_new_json(path: Path, body: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FreeBindError(
            f"binding record already exists: {path.name}",
            code="free_bind_exists",
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(body, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.link(temporary, path)
    except FileExistsError as error:
        raise FreeBindError(
            f"binding record already exists: {path.name}",
            code="free_bind_exists",
        ) from error
    finally:
        temporary.unlink(missing_ok=True)


def _load_proposal(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise FreeBindError("binding proposal must not be a symlink")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FreeBindError(
            "binding proposal is unreadable",
            code="free_bind_missing",
        ) from error
    if not isinstance(body, dict) or set(body) != PROPOSAL_FIELDS:
        raise FreeBindError("binding proposal fields are invalid")
    if body["schema_version"] != BINDING_SCHEMA_VERSION:
        raise FreeBindError("binding proposal schema_version is invalid")
    if body["require_native_server"] is not True:
        raise FreeBindError("binding proposal must require native servers")
    if body["live_authority"] is not False:
        raise FreeBindError("binding proposal cannot grant live authority")
    selection = _selection(
        body["binding_id"],
        body["revision"],
        body["family_id"],
        body["cell_ids"],
        body["notes"],
    )
    if path.stem != selection.binding_id:
        raise FreeBindError("binding proposal ID must match filename")
    _utc_timestamp(body["created_at"], "binding proposal created_at")
    _source_hashes(body["source_hashes"])
    _hash_value(body["machine_profile_hash"], "binding machine_profile_hash")
    _hash_value(body["proposal_hash"], "binding proposal_hash")
    expected_hash = _canonical_hash(_proposal_body(body))
    if body["proposal_hash"] != expected_hash:
        raise FreeBindError(
            "binding proposal hash mismatch",
            code="free_bind_hash_mismatch",
        )
    return body


def _evaluate(
    proposal: dict[str, object],
    *,
    machine_profile_path: Path,
    repository_root: Path,
    families_root: Path,
    cells_root: Path,
) -> dict[str, object]:
    selection = _selection(
        proposal["binding_id"],
        proposal["revision"],
        proposal["family_id"],
        proposal["cell_ids"],
        proposal["notes"],
    )
    _, cells, source_hashes = _load_cells(
        selection,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=cells_root,
    )
    roots = load_artifact_roots(machine_profile_path)
    profile_hash = _sha256(machine_profile_path)
    findings = _artifact_findings(cells, roots)
    inputs_match = (
        proposal["source_hashes"] == source_hashes
        and proposal["machine_profile_hash"] == profile_hash
    )
    artifacts_ready = all(item["status"] == "PRESENT" for item in findings)
    if not inputs_match:
        status = STATUS_STALE
        next_action = "Create a new proposal because a bound input changed."
    elif not artifacts_ready:
        status = STATUS_ACTION_REQUIRED
        next_action = "Repair the approved artifact roots, then validate again."
    else:
        status = STATUS_READY
        next_action = "Review this proposal, then explicitly adopt it if correct."
    return {
        "artifacts": findings,
        "binding_id": selection.binding_id,
        "cell_ids": list(selection.cell_ids),
        "family_id": selection.family_id,
        "inputs_match": inputs_match,
        "live_authority": False,
        "live_status": LIVE_STATUS_NOT_CHECKED,
        "next_action": next_action,
        "proposal_hash": proposal["proposal_hash"],
        "ready_for_adoption": status == STATUS_READY,
        "revision": selection.revision,
        "status": status,
    }


def propose_binding(
    *,
    binding_id: str,
    revision: str,
    family_id: str,
    cell_ids: Sequence[str],
    notes: str,
    state_dir: Path,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Write one immutable local proposal and return its current validation."""

    selection = _selection(binding_id, revision, family_id, cell_ids, notes)
    resolved_cells_root = cells_root or repository_root / "config" / "matrix" / "cells"
    _, _, source_hashes = _load_cells(
        selection,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=resolved_cells_root,
    )
    # Loading the roots validates the fixed local profile before persistence.
    load_artifact_roots(machine_profile_path)
    proposal: dict[str, object] = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "binding_id": selection.binding_id,
        "revision": selection.revision,
        "family_id": selection.family_id,
        "cell_ids": list(selection.cell_ids),
        "notes": selection.notes,
        "require_native_server": True,
        "created_at": _utc_now(now),
        "source_hashes": source_hashes,
        "machine_profile_hash": _sha256(machine_profile_path),
        "live_authority": False,
    }
    proposal["proposal_hash"] = _canonical_hash(proposal)
    _write_new_json(_proposal_path(state_dir, selection.binding_id), proposal)
    return _evaluate(
        proposal,
        machine_profile_path=machine_profile_path,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=resolved_cells_root,
    )


def validate_binding_proposal(
    binding_id: str,
    *,
    state_dir: Path,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
) -> dict[str, object]:
    resolved_id = _safe_binding_id(binding_id)
    proposal = _load_proposal(_proposal_path(state_dir, resolved_id))
    return _evaluate(
        proposal,
        machine_profile_path=machine_profile_path,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=cells_root or repository_root / "config" / "matrix" / "cells",
    )


def show_binding_proposal(
    binding_id: str,
    *,
    state_dir: Path,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
) -> dict[str, object]:
    resolved_id = _safe_binding_id(binding_id)
    proposal = _load_proposal(_proposal_path(state_dir, resolved_id))
    validation = _evaluate(
        proposal,
        machine_profile_path=machine_profile_path,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=cells_root or repository_root / "config" / "matrix" / "cells",
    )
    adoption_path = _adopted_path(state_dir, resolved_id)
    adoption = (
        load_adopted_binding(resolved_id, state_dir=state_dir)
        if adoption_path.exists() or adoption_path.is_symlink()
        else None
    )
    return {
        "adoption": adoption,
        "proposal": proposal,
        "validation": validation,
    }


def adopt_binding(
    binding_id: str,
    *,
    state_dir: Path,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Explicitly adopt a validated declaration without granting live authority."""

    resolved_id = _safe_binding_id(binding_id)
    proposal = _load_proposal(_proposal_path(state_dir, resolved_id))
    validation = _evaluate(
        proposal,
        machine_profile_path=machine_profile_path,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=cells_root or repository_root / "config" / "matrix" / "cells",
    )
    if validation["status"] != STATUS_READY:
        raise FreeBindError(
            "binding proposal is not ready for adoption",
            code="free_bind_not_ready",
        )
    binding = _binding_body(proposal)
    record: dict[str, object] = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "adopted_at": _utc_now(now),
        "binding": binding,
        "binding_hash": _canonical_hash(binding),
        "proposal_hash": proposal["proposal_hash"],
        "live_authority": False,
    }
    _write_new_json(_adopted_path(state_dir, resolved_id), record)
    return {
        "adopted_at": record["adopted_at"],
        "binding_hash": record["binding_hash"],
        "binding_id": resolved_id,
        "cell_ids": binding["cell_ids"],
        "family_id": binding["family_id"],
        "live_authority": False,
        "live_status": LIVE_STATUS_NOT_CHECKED,
        "proposal_hash": record["proposal_hash"],
        "status": "ADOPTED_OFFLINE",
    }


def load_adopted_binding(
    binding_id: str,
    *,
    state_dir: Path,
) -> dict[str, object]:
    """Load and hash-check an adopted declaration for a future planner."""

    resolved_id = _safe_binding_id(binding_id)
    path = _adopted_path(state_dir, resolved_id)
    if path.is_symlink():
        raise FreeBindError("adopted binding must not be a symlink")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FreeBindError(
            "adopted binding is unreadable",
            code="free_bind_adoption_missing",
        ) from error
    if not isinstance(record, dict) or set(record) != ADOPTION_FIELDS:
        raise FreeBindError("adopted binding fields are invalid")
    if record["schema_version"] != BINDING_SCHEMA_VERSION:
        raise FreeBindError("adopted binding schema_version is invalid")
    if record["live_authority"] is not False:
        raise FreeBindError("adopted binding cannot grant live authority")
    _utc_timestamp(record["adopted_at"], "adopted binding adopted_at")
    _hash_value(record["binding_hash"], "adopted binding binding_hash")
    _hash_value(record["proposal_hash"], "adopted binding proposal_hash")
    binding = record["binding"]
    if not isinstance(binding, dict) or set(binding) != BINDING_FIELDS:
        raise FreeBindError("adopted binding declaration is invalid")
    selection = _selection(
        binding["binding_id"],
        binding["revision"],
        binding["family_id"],
        binding["cell_ids"],
        binding["notes"],
    )
    if selection.binding_id != resolved_id:
        raise FreeBindError("adopted binding ID mismatch")
    if binding["require_native_server"] is not True:
        raise FreeBindError("adopted binding must require native servers")
    _source_hashes(binding["source_hashes"])
    _hash_value(binding["machine_profile_hash"], "binding machine_profile_hash")
    if record["binding_hash"] != _canonical_hash(binding):
        raise FreeBindError(
            "adopted binding hash mismatch",
            code="free_bind_hash_mismatch",
        )
    return record


def validate_adopted_binding(
    binding_id: str,
    *,
    state_dir: Path,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
) -> dict[str, object]:
    """Revalidate an adopted declaration before immutable planning."""

    resolved_id = _safe_binding_id(binding_id)
    record = load_adopted_binding(resolved_id, state_dir=state_dir)
    proposal = _load_proposal(_proposal_path(state_dir, resolved_id))
    binding = record["binding"]
    if not isinstance(binding, dict):
        raise FreeBindError("adopted binding declaration is invalid")
    if record["proposal_hash"] != proposal["proposal_hash"] or binding != _binding_body(
        proposal
    ):
        raise FreeBindError(
            "adopted binding no longer matches its proposal",
            code="free_bind_adoption_mismatch",
        )
    selection = _selection(
        binding["binding_id"],
        binding["revision"],
        binding["family_id"],
        binding["cell_ids"],
        binding["notes"],
    )
    resolved_cells_root = cells_root or repository_root / "config" / "matrix" / "cells"
    _, cells, source_hashes = _load_cells(
        selection,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=resolved_cells_root,
    )
    roots = load_artifact_roots(machine_profile_path)
    if binding["source_hashes"] != source_hashes or binding[
        "machine_profile_hash"
    ] != _sha256(machine_profile_path):
        raise FreeBindError(
            "adopted binding inputs changed; create and adopt a new version",
            code="free_bind_stale",
        )
    findings = _artifact_findings(cells, roots)
    if not all(item["status"] == "PRESENT" for item in findings):
        raise FreeBindError(
            "adopted binding artifacts are not ready",
            code="free_bind_not_ready",
        )
    return record
