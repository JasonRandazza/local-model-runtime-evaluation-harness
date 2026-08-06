"""Strict checked-in declarations for heterogeneous managed comparisons."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .matrix_config import (
    DEFAULT_FAMILIES_ROOT,
    REPOSITORY_ROOT,
    Cell,
    MatrixError,
    MatrixSuite,
    ModelFamily,
    load_family,
)
from .preference_config import PreferenceError, PreferenceSuite
from .rag_config import RagCorpus, RagError, RagSuite


DEFAULT_OPEN_MIXES_ROOT = REPOSITORY_ROOT / "config" / "open-mixes"
DEFAULT_SUITE_CONTRACTS_ROOT = (
    REPOSITORY_ROOT / "config" / "open-mix-suite-contracts"
)
DEFAULT_CELLS_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "cells"
SAFE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SAFE_CELL_ID = re.compile(r"[a-z0-9][a-z0-9_-]*__(?:osaurus|omlx|optiq)")

OPEN_MIX_FIELDS = frozenset(
    {
        "schema_version",
        "open_mix_id",
        "revision",
        "members",
        "suite_contract_id",
        "estimated_minutes",
        "notes",
    }
)
MEMBER_FIELDS = frozenset({"family_id", "cell_id"})
SUITE_CONTRACT_FIELDS = frozenset(
    {
        "schema_version",
        "suite_contract_id",
        "revision",
        "matrix_suite_path",
        "preference_suite_path",
        "rag_suite_path",
        "rag_corpus_path",
        "notes",
    }
)


class OpenMixError(RuntimeError):
    def __init__(self, message: str, *, code: str = "open_mix_invalid") -> None:
        super().__init__(message)
        self.code = code


def _safe_id(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 80
        or not SAFE_ID.fullmatch(value)
    ):
        raise OpenMixError(f"{label} is invalid")
    return value


def _revision(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.isdecimal() or int(value) < 1:
        raise OpenMixError(f"{label} revision is invalid")
    return value


def _contained_regular_file(path: Path, root: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise OpenMixError(f"{label} must be a regular file")
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise OpenMixError(f"{label} escaped its approved root")
    return resolved


def _repo_path(
    value: object,
    *,
    repository_root: Path,
    expected_prefix: PurePosixPath,
    label: str,
    require_directory: bool = False,
) -> Path:
    if not isinstance(value, str) or not value:
        raise OpenMixError(f"{label} is invalid")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or tuple(relative.parts[: len(expected_prefix.parts)])
        != expected_prefix.parts
    ):
        raise OpenMixError(f"{label} is invalid")
    unresolved = repository_root / Path(relative)
    if unresolved.is_symlink():
        raise OpenMixError(f"{label} must not be a symlink")
    resolved = unresolved.resolve()
    if not resolved.is_relative_to(repository_root.resolve()):
        raise OpenMixError(f"{label} escaped repository")
    if require_directory:
        if not resolved.is_dir():
            raise OpenMixError(f"{label} directory is missing")
    elif not resolved.is_file():
        raise OpenMixError(f"{label} file is missing")
    return resolved


@dataclass(frozen=True)
class OpenMixSuiteContract:
    suite_contract_id: str
    revision: str
    matrix_suite_path: Path
    preference_suite_path: Path
    rag_suite_path: Path
    rag_corpus_path: Path
    notes: str
    path: Path
    matrix_suite: MatrixSuite
    preference_suite: PreferenceSuite
    rag_suite: RagSuite

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        repository_root: Path = REPOSITORY_ROOT,
    ) -> OpenMixSuiteContract:
        if path.is_symlink():
            raise OpenMixError("suite contract must not be a symlink")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise OpenMixError(
                "suite contract JSON is unreadable",
                code="open_mix_suite_contract_unreadable",
            ) from error
        if not isinstance(data, dict) or set(data) != SUITE_CONTRACT_FIELDS:
            raise OpenMixError("suite contract fields are invalid")
        if data["schema_version"] != "1.0.0":
            raise OpenMixError("suite contract schema_version is invalid")
        contract_id = _safe_id(data["suite_contract_id"], "suite_contract_id")
        if path.stem != contract_id:
            raise OpenMixError("suite_contract_id must match filename")
        revision = _revision(data["revision"], "suite contract")
        if not isinstance(data["notes"], str):
            raise OpenMixError("suite contract notes are invalid")

        matrix_path = _repo_path(
            data["matrix_suite_path"],
            repository_root=repository_root,
            expected_prefix=PurePosixPath("suites"),
            label="matrix_suite_path",
        )
        preference_path = _repo_path(
            data["preference_suite_path"],
            repository_root=repository_root,
            expected_prefix=PurePosixPath("suites"),
            label="preference_suite_path",
        )
        rag_path = _repo_path(
            data["rag_suite_path"],
            repository_root=repository_root,
            expected_prefix=PurePosixPath("suites"),
            label="rag_suite_path",
        )
        corpus_path = _repo_path(
            data["rag_corpus_path"],
            repository_root=repository_root,
            expected_prefix=PurePosixPath("corpora"),
            label="rag_corpus_path",
            require_directory=True,
        )
        try:
            matrix_suite = MatrixSuite.load(matrix_path)
            preference_suite = PreferenceSuite.load(preference_path)
            rag_suite = RagSuite.load(rag_path)
            corpus = RagCorpus.load(corpus_path)
        except (MatrixError, PreferenceError, RagError, OSError) as error:
            raise OpenMixError("suite contract inputs are invalid") from error
        if corpus.corpus_id != rag_suite.corpus_id:
            raise OpenMixError("suite contract RAG corpus mismatch")
        return cls(
            suite_contract_id=contract_id,
            revision=revision,
            matrix_suite_path=matrix_path,
            preference_suite_path=preference_path,
            rag_suite_path=rag_path,
            rag_corpus_path=corpus_path,
            notes=data["notes"],
            path=path.resolve(),
            matrix_suite=matrix_suite,
            preference_suite=preference_suite,
            rag_suite=rag_suite,
        )


@dataclass(frozen=True)
class OpenMixMember:
    family_id: str
    cell_id: str
    family: ModelFamily
    cell: Cell
    family_path: Path
    cell_path: Path


@dataclass(frozen=True)
class OpenMix:
    open_mix_id: str
    revision: str
    members: tuple[OpenMixMember, ...]
    suite_contract: OpenMixSuiteContract
    estimated_minutes: int
    notes: str
    path: Path

    @property
    def family_ids(self) -> tuple[str, ...]:
        return tuple(member.family_id for member in self.members)

    @property
    def cell_ids(self) -> tuple[str, ...]:
        return tuple(member.cell_id for member in self.members)

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        repository_root: Path = REPOSITORY_ROOT,
        families_root: Path = DEFAULT_FAMILIES_ROOT,
        cells_root: Path | None = None,
        suite_contracts_root: Path | None = None,
    ) -> OpenMix:
        if path.is_symlink():
            raise OpenMixError("open mix must not be a symlink")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise OpenMixError(
                "open mix JSON is unreadable",
                code="open_mix_unreadable",
            ) from error
        if not isinstance(data, dict) or set(data) != OPEN_MIX_FIELDS:
            raise OpenMixError("open mix fields are invalid")
        if data["schema_version"] != "1.0.0":
            raise OpenMixError("open mix schema_version is invalid")
        mix_id = _safe_id(data["open_mix_id"], "open_mix_id")
        if path.stem != mix_id:
            raise OpenMixError("open_mix_id must match filename")
        revision = _revision(data["revision"], "open mix")
        if not isinstance(data["notes"], str):
            raise OpenMixError("open mix notes are invalid")
        if (
            type(data["estimated_minutes"]) is not int
            or not 1 <= data["estimated_minutes"] <= 1440
        ):
            raise OpenMixError("open mix estimated_minutes is invalid")
        raw_members = data["members"]
        if not isinstance(raw_members, list) or not 2 <= len(raw_members) <= 6:
            raise OpenMixError("open mix must contain two to six members")

        resolved_cells_root = cells_root or repository_root / "config/matrix/cells"
        members: list[OpenMixMember] = []
        seen_cells: set[str] = set()
        for raw_member in raw_members:
            if not isinstance(raw_member, dict) or set(raw_member) != MEMBER_FIELDS:
                raise OpenMixError("open mix member fields are invalid")
            family_id = _safe_id(raw_member["family_id"], "member family_id")
            cell_id = raw_member["cell_id"]
            if (
                not isinstance(cell_id, str)
                or len(cell_id) > 100
                or not SAFE_CELL_ID.fullmatch(cell_id)
            ):
                raise OpenMixError("member cell_id is invalid")
            if cell_id in seen_cells:
                raise OpenMixError("open mix member cells must be unique")
            seen_cells.add(cell_id)
            family_path = _contained_regular_file(
                families_root / f"{family_id}.json",
                families_root,
                "member family",
            )
            cell_path = _contained_regular_file(
                resolved_cells_root / f"{cell_id}.json",
                resolved_cells_root,
                "member cell",
            )
            try:
                family = load_family(family_id, families_root=families_root)
                cell = Cell.load(
                    cell_path,
                    family=family,
                    require_native_server=True,
                )
            except (MatrixError, OSError, ValueError, KeyError, TypeError) as error:
                raise OpenMixError("open mix member is invalid") from error
            if cell.cell_id != cell_id:
                raise OpenMixError("member cell_id must match filename")
            members.append(
                OpenMixMember(
                    family_id=family_id,
                    cell_id=cell_id,
                    family=family,
                    cell=cell,
                    family_path=family_path,
                    cell_path=cell_path,
                )
            )
        if len({member.family_id for member in members}) < 2:
            raise OpenMixError("open mix must contain at least two families")

        contract_id = _safe_id(data["suite_contract_id"], "suite_contract_id")
        contracts_root = (
            suite_contracts_root
            or repository_root / "config/open-mix-suite-contracts"
        )
        contract_path = _contained_regular_file(
            contracts_root / f"{contract_id}.json",
            contracts_root,
            "suite contract",
        )
        suite_contract = OpenMixSuiteContract.load(
            contract_path,
            repository_root=repository_root,
        )
        return cls(
            open_mix_id=mix_id,
            revision=revision,
            members=tuple(members),
            suite_contract=suite_contract,
            estimated_minutes=data["estimated_minutes"],
            notes=data["notes"],
            path=path.resolve(),
        )


def load_open_mix(
    open_mix_id: str,
    *,
    root: Path = DEFAULT_OPEN_MIXES_ROOT,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
    suite_contracts_root: Path | None = None,
) -> OpenMix:
    resolved_id = _safe_id(open_mix_id, "open_mix_id")
    path = root / f"{resolved_id}.json"
    if not path.is_file() or path.is_symlink():
        raise OpenMixError(
            f"open mix is unknown: {resolved_id}",
            code="open_mix_missing",
        )
    return OpenMix.load(
        path,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=cells_root,
        suite_contracts_root=suite_contracts_root,
    )
