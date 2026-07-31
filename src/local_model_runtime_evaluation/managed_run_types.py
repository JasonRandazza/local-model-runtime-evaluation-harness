"""Immutable shared types for managed local runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .operator_policy import PolicyRequest


MANAGED_PLAN_SCHEMA_VERSION = "1.0.0"


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
    steps: tuple[ManagedStep, ...]
    cell_ids: tuple[str, ...]
    pair_ids: tuple[str, ...]
    matrix_mode: str
    campaign_path: str
    suite_paths: tuple[tuple[str, str], ...]
    rag_corpus_path: str
    cells_root: str
    pairs_root: str
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
            "endpoints": list(self.endpoints),
            "runtimes": sorted(self.runtimes),
            "request_count": self.request_count,
            "estimated_minutes": self.estimated_minutes,
            "memory_floor_percent": self.memory_floor_percent,
            "max_parallel_models": self.max_parallel_models,
            "created_at": self.created_at,
        }
        if include_hash:
            body["plan_hash"] = self.plan_hash
        return body

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManagedRunPlan:
        expected = {
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
            "endpoints",
            "runtimes",
            "request_count",
            "estimated_minutes",
            "memory_floor_percent",
            "max_parallel_models",
            "created_at",
            "plan_hash",
        }
        if set(data) != expected:
            raise ValueError("managed run plan fields are invalid")
        identity = data["identity"]
        suite_paths = data["suite_paths"]
        sequence_fields = (
            "steps",
            "cell_ids",
            "pair_ids",
            "endpoints",
            "runtimes",
        )
        if not isinstance(identity, dict) or not isinstance(suite_paths, dict):
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
        try:
            steps = tuple(ManagedStep(value) for value in data["steps"])
        except (TypeError, ValueError) as error:
            raise ValueError("managed run plan step is invalid") from error
        for field in ("cell_ids", "pair_ids", "endpoints", "runtimes"):
            if not all(isinstance(value, str) for value in data[field]):
                raise ValueError(f"managed run plan {field} is invalid")
        return cls(
            schema_version=data["schema_version"],
            identity=RunIdentity.from_dict(identity),
            recipe_id=data["recipe_id"],
            family_id=data["family_id"],
            steps=steps,
            cell_ids=tuple(data["cell_ids"]),
            pair_ids=tuple(data["pair_ids"]),
            matrix_mode=data["matrix_mode"],
            campaign_path=data["campaign_path"],
            suite_paths=tuple(
                (str(key), str(value))
                for key, value in sorted(suite_paths.items())
            ),
            rag_corpus_path=data["rag_corpus_path"],
            cells_root=data["cells_root"],
            pairs_root=data["pairs_root"],
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
