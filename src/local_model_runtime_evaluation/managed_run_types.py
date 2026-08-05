"""Immutable shared types for managed local runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from pathlib import PurePosixPath
from typing import Any

from .operator_policy import PolicyRequest


LEGACY_MANAGED_PLAN_SCHEMA_VERSION = "1.0.0"
COMPARISON_CLASS_PLAN_SCHEMA_VERSION = "1.1.0"
MANAGED_PLAN_SCHEMA_VERSION = "1.2.0"
SUPPORTED_MANAGED_PLAN_SCHEMA_VERSIONS = frozenset(
    {
        LEGACY_MANAGED_PLAN_SCHEMA_VERSION,
        COMPARISON_CLASS_PLAN_SCHEMA_VERSION,
        MANAGED_PLAN_SCHEMA_VERSION,
    }
)
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
SAFE_COMPARISON_CLASS_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class ManagedStep(StrEnum):
    PREFLIGHT = "preflight"
    MATRIX = "matrix"
    PREFERENCE = "preference"
    RAG_ORACLE = "rag-oracle"
    RAG_KEYWORD = "rag-keyword"
    OVERHEAD = "overhead"
    SEAL = "seal"


class StepState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED_PROVIDER_RECONNECT = "BLOCKED_PROVIDER_RECONNECT"
    STOPPED = "STOPPED"
    INCOMPARABLE = "INCOMPARABLE"


class RunSummaryState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    STOPPED = "STOPPED"
    PARTIAL_BLOCKED = "PARTIAL_BLOCKED"


class Ownership(StrEnum):
    ATTACHED = "attached"
    OWNED = "owned"
    RECLAIMED = "reclaimed"


@dataclass(frozen=True)
class RunIdentity:
    run_name: str
    run_id: str
    attempt: int
    comparison_id: str
    parent_run_id: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_name": self.run_name,
            "run_id": self.run_id,
            "attempt": self.attempt,
            "comparison_id": self.comparison_id,
            "parent_run_id": self.parent_run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RunIdentity:
        expected = {
            "run_name",
            "run_id",
            "attempt",
            "comparison_id",
            "parent_run_id",
        }
        if set(data) != expected:
            raise ValueError("run identity fields are invalid")
        parent = data["parent_run_id"]
        if parent is not None and not isinstance(parent, str):
            raise ValueError("parent_run_id is invalid")
        if (
            not isinstance(data["run_name"], str)
            or not isinstance(data["run_id"], str)
            or type(data["attempt"]) is not int
            or not isinstance(data["comparison_id"], str)
        ):
            raise ValueError("run identity values are invalid")
        return cls(
            run_name=data["run_name"],
            run_id=data["run_id"],
            attempt=data["attempt"],
            comparison_id=data["comparison_id"],
            parent_run_id=parent,
        )


@dataclass(frozen=True)
class ManagedRunPlan:
    schema_version: str
    identity: RunIdentity
    recipe_id: str
    family_id: str
    comparison_class_id: str | None
    comparison_class_path: str | None
    binding_id: str | None
    binding_revision: str | None
    binding_hash: str | None
    binding_proposal_hash: str | None
    baseline_cell_ids: tuple[str, ...]
    steps: tuple[ManagedStep, ...]
    cell_ids: tuple[str, ...]
    pair_ids: tuple[str, ...]
    matrix_mode: str
    campaign_path: str
    suite_paths: tuple[tuple[str, str], ...]
    rag_corpus_path: str
    cells_root: str
    pairs_root: str
    input_hashes: tuple[tuple[str, str], ...]
    endpoints: tuple[str, ...]
    runtimes: frozenset[str]
    request_count: int
    estimated_minutes: int
    memory_floor_percent: int
    max_parallel_models: int
    created_at: str
    plan_hash: str

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        body: dict[str, object] = {
            "schema_version": self.schema_version,
            "identity": self.identity.to_dict(),
            "recipe_id": self.recipe_id,
            "family_id": self.family_id,
            "steps": [step.value for step in self.steps],
            "cell_ids": list(self.cell_ids),
            "pair_ids": list(self.pair_ids),
            "matrix_mode": self.matrix_mode,
            "campaign_path": self.campaign_path,
            "suite_paths": dict(self.suite_paths),
            "rag_corpus_path": self.rag_corpus_path,
            "cells_root": self.cells_root,
            "pairs_root": self.pairs_root,
            "input_hashes": dict(self.input_hashes),
            "endpoints": list(self.endpoints),
            "runtimes": sorted(self.runtimes),
            "request_count": self.request_count,
            "estimated_minutes": self.estimated_minutes,
            "memory_floor_percent": self.memory_floor_percent,
            "max_parallel_models": self.max_parallel_models,
            "created_at": self.created_at,
        }
        if self.schema_version != LEGACY_MANAGED_PLAN_SCHEMA_VERSION:
            body.update(
                comparison_class_id=self.comparison_class_id,
                comparison_class_path=self.comparison_class_path,
                baseline_cell_ids=list(self.baseline_cell_ids),
            )
        if self.schema_version == MANAGED_PLAN_SCHEMA_VERSION:
            body.update(
                binding_id=self.binding_id,
                binding_revision=self.binding_revision,
                binding_hash=self.binding_hash,
                binding_proposal_hash=self.binding_proposal_hash,
            )
        if include_hash:
            body["plan_hash"] = self.plan_hash
        return body

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManagedRunPlan:
        legacy_expected = {
            "schema_version",
            "identity",
            "recipe_id",
            "family_id",
            "steps",
            "cell_ids",
            "pair_ids",
            "matrix_mode",
            "campaign_path",
            "suite_paths",
            "rag_corpus_path",
            "cells_root",
            "pairs_root",
            "input_hashes",
            "endpoints",
            "runtimes",
            "request_count",
            "estimated_minutes",
            "memory_floor_percent",
            "max_parallel_models",
            "created_at",
            "plan_hash",
        }
        comparison_class_expected = legacy_expected | {
            "comparison_class_id",
            "comparison_class_path",
            "baseline_cell_ids",
        }
        current_expected = comparison_class_expected | {
            "binding_id",
            "binding_revision",
            "binding_hash",
            "binding_proposal_hash",
        }
        schema_version = data.get("schema_version")
        if schema_version not in SUPPORTED_MANAGED_PLAN_SCHEMA_VERSIONS:
            raise ValueError("managed run plan schema_version is invalid")
        if schema_version == LEGACY_MANAGED_PLAN_SCHEMA_VERSION:
            expected = legacy_expected
        elif schema_version == COMPARISON_CLASS_PLAN_SCHEMA_VERSION:
            expected = comparison_class_expected
        else:
            expected = current_expected
        if set(data) != expected:
            raise ValueError("managed run plan fields are invalid")
        identity = data["identity"]
        suite_paths = data["suite_paths"]
        input_hashes = data["input_hashes"]
        sequence_fields = (
            "steps",
            "cell_ids",
            "pair_ids",
            "endpoints",
            "runtimes",
        )
        if schema_version != LEGACY_MANAGED_PLAN_SCHEMA_VERSION:
            sequence_fields = sequence_fields + ("baseline_cell_ids",)
        if (
            not isinstance(identity, dict)
            or not isinstance(suite_paths, dict)
            or not isinstance(input_hashes, dict)
        ):
            raise ValueError("managed run plan object field is invalid")
        if any(not isinstance(data[field], list) for field in sequence_fields):
            raise ValueError("managed run plan sequence field is invalid")
        scalar_strings = (
            "schema_version",
            "recipe_id",
            "family_id",
            "matrix_mode",
            "campaign_path",
            "rag_corpus_path",
            "cells_root",
            "pairs_root",
            "created_at",
            "plan_hash",
        )
        if any(not isinstance(data[field], str) for field in scalar_strings):
            raise ValueError("managed run plan string field is invalid")
        integer_fields = (
            "request_count",
            "estimated_minutes",
            "memory_floor_percent",
            "max_parallel_models",
        )
        if any(type(data[field]) is not int for field in integer_fields):
            raise ValueError("managed run plan integer field is invalid")
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in suite_paths.items()
        ):
            raise ValueError("managed run suite_paths is invalid")
        if not input_hashes or not all(
            isinstance(path, str)
            and path
            and not PurePosixPath(path).is_absolute()
            and ".." not in PurePosixPath(path).parts
            and isinstance(digest, str)
            and SHA256_HEX.fullmatch(digest)
            for path, digest in input_hashes.items()
        ):
            raise ValueError("managed run input_hashes is invalid")
        try:
            steps = tuple(ManagedStep(value) for value in data["steps"])
        except (TypeError, ValueError) as error:
            raise ValueError("managed run plan step is invalid") from error
        for field_name in ("cell_ids", "pair_ids", "endpoints", "runtimes"):
            if not all(isinstance(value, str) for value in data[field_name]):
                raise ValueError(f"managed run plan {field_name} is invalid")
        if schema_version == LEGACY_MANAGED_PLAN_SCHEMA_VERSION:
            comparison_class_id = None
            comparison_class_path = None
            binding_id = None
            binding_revision = None
            binding_hash = None
            binding_proposal_hash = None
            baseline_cell_ids = tuple(data["cell_ids"])
        else:
            comparison_class_id = data["comparison_class_id"]
            comparison_class_path = data["comparison_class_path"]
            if (comparison_class_id is None) != (comparison_class_path is None):
                raise ValueError("managed run comparison class fields are invalid")
            if comparison_class_id is not None and (
                not isinstance(comparison_class_id, str)
                or not isinstance(comparison_class_path, str)
                or not comparison_class_id
                or not comparison_class_path
                or len(comparison_class_id) > 80
                or not SAFE_COMPARISON_CLASS_ID.fullmatch(comparison_class_id)
                or PurePosixPath(comparison_class_path).is_absolute()
                or ".." in PurePosixPath(comparison_class_path).parts
                or comparison_class_path
                != f"config/comparison-classes/{comparison_class_id}.json"
            ):
                raise ValueError("managed run comparison class fields are invalid")
            baseline_cell_ids = tuple(data["baseline_cell_ids"])
            if (
                len(baseline_cell_ids) != 3
                or len(set(baseline_cell_ids)) != 3
                or not all(
                    isinstance(value, str) and value for value in baseline_cell_ids
                )
            ):
                raise ValueError("managed run baseline_cell_ids is invalid")
            if schema_version == COMPARISON_CLASS_PLAN_SCHEMA_VERSION:
                binding_id = None
                binding_revision = None
                binding_hash = None
                binding_proposal_hash = None
            else:
                binding_id = data["binding_id"]
                binding_revision = data["binding_revision"]
                binding_hash = data["binding_hash"]
                binding_proposal_hash = data["binding_proposal_hash"]
                binding_values = (
                    binding_id,
                    binding_revision,
                    binding_hash,
                    binding_proposal_hash,
                )
                if any(value is None for value in binding_values) and not all(
                    value is None for value in binding_values
                ):
                    raise ValueError("managed run binding fields are invalid")
                if binding_id is not None and (
                    not isinstance(binding_id, str)
                    or len(binding_id) > 80
                    or not SAFE_COMPARISON_CLASS_ID.fullmatch(binding_id)
                    or not isinstance(binding_revision, str)
                    or not binding_revision.isdecimal()
                    or int(binding_revision) < 1
                    or not isinstance(binding_hash, str)
                    or not SHA256_HEX.fullmatch(binding_hash)
                    or not isinstance(binding_proposal_hash, str)
                    or not SHA256_HEX.fullmatch(binding_proposal_hash)
                ):
                    raise ValueError("managed run binding fields are invalid")
            if comparison_class_id is not None and binding_id is not None:
                raise ValueError("managed run declarations are mutually exclusive")
            if comparison_class_id is not None:
                if (
                    tuple(data["cell_ids"][: len(baseline_cell_ids)])
                    != baseline_cell_ids
                ):
                    raise ValueError(
                        "managed run baseline cells must be preserved in order"
                    )
            elif binding_id is not None:
                selected = tuple(data["cell_ids"])
                if (
                    len(selected) < 2
                    or len(selected) > 9
                    or len(set(selected)) != len(selected)
                    or not all(isinstance(value, str) and value for value in selected)
                ):
                    raise ValueError("managed run binding cells are invalid")
            elif tuple(data["cell_ids"]) != baseline_cell_ids:
                raise ValueError("managed run undeclared cells are invalid")
        return cls(
            schema_version=data["schema_version"],
            identity=RunIdentity.from_dict(identity),
            recipe_id=data["recipe_id"],
            family_id=data["family_id"],
            comparison_class_id=comparison_class_id,
            comparison_class_path=comparison_class_path,
            binding_id=binding_id,
            binding_revision=binding_revision,
            binding_hash=binding_hash,
            binding_proposal_hash=binding_proposal_hash,
            baseline_cell_ids=baseline_cell_ids,
            steps=steps,
            cell_ids=tuple(data["cell_ids"]),
            pair_ids=tuple(data["pair_ids"]),
            matrix_mode=data["matrix_mode"],
            campaign_path=data["campaign_path"],
            suite_paths=tuple(
                (str(key), str(value)) for key, value in sorted(suite_paths.items())
            ),
            rag_corpus_path=data["rag_corpus_path"],
            cells_root=data["cells_root"],
            pairs_root=data["pairs_root"],
            input_hashes=tuple(
                (str(path), str(digest))
                for path, digest in sorted(input_hashes.items())
            ),
            endpoints=tuple(data["endpoints"]),
            runtimes=frozenset(data["runtimes"]),
            request_count=data["request_count"],
            estimated_minutes=data["estimated_minutes"],
            memory_floor_percent=data["memory_floor_percent"],
            max_parallel_models=data["max_parallel_models"],
            created_at=data["created_at"],
            plan_hash=data["plan_hash"],
        )

    def suite_path(self, step: ManagedStep) -> str:
        suites = dict(self.suite_paths)
        try:
            return suites[step.value]
        except KeyError as error:
            raise ValueError(f"suite path missing for {step.value}") from error

    def policy_request(self) -> PolicyRequest:
        return PolicyRequest(
            runtimes=self.runtimes,
            endpoints=self.endpoints,
            inference=True,
            start=True,
            exact_reclaim=True,
            parallel_models=self.max_parallel_models,
            memory_floor_percent=self.memory_floor_percent,
            estimated_minutes=self.estimated_minutes,
            request_count=self.request_count,
        )


@dataclass(frozen=True)
class StepRecord:
    step: ManagedStep
    state: StepState
    attempt: int
    output_path: str | None = None
    detail: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "step": self.step.value,
            "state": self.state.value,
            "attempt": self.attempt,
            "output_path": self.output_path,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ManagedRunState:
    run_id: str
    attempt: int
    summary_state: RunSummaryState
    steps: tuple[StepRecord, ...]
    cleanup_complete: bool
    sealed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "attempt": self.attempt,
            "summary_state": self.summary_state.value,
            "steps": [step.to_dict() for step in self.steps],
            "cleanup_complete": self.cleanup_complete,
            "sealed": self.sealed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManagedRunState:
        expected = {
            "run_id",
            "attempt",
            "summary_state",
            "steps",
            "cleanup_complete",
            "sealed",
        }
        if set(data) != expected or not isinstance(data["steps"], list):
            raise ValueError("managed run state fields are invalid")
        records: list[StepRecord] = []
        for raw in data["steps"]:
            if not isinstance(raw, dict) or set(raw) != {
                "step",
                "state",
                "attempt",
                "output_path",
                "detail",
            }:
                raise ValueError("managed step record is invalid")
            detail = raw["detail"]
            output_path = raw["output_path"]
            if not isinstance(detail, dict):
                raise ValueError("managed step detail is invalid")
            if output_path is not None and not isinstance(output_path, str):
                raise ValueError("managed step output_path is invalid")
            records.append(
                StepRecord(
                    step=ManagedStep(raw["step"]),
                    state=StepState(raw["state"]),
                    attempt=int(raw["attempt"]),
                    output_path=output_path,
                    detail=detail,
                )
            )
        return cls(
            run_id=str(data["run_id"]),
            attempt=int(data["attempt"]),
            summary_state=RunSummaryState(data["summary_state"]),
            steps=tuple(records),
            cleanup_complete=bool(data["cleanup_complete"]),
            sealed=bool(data["sealed"]),
        )
