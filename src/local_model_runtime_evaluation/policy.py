from __future__ import annotations

from pathlib import Path

from .manifest import CANONICAL_OUTPUT_ROOT
from .models import BenchmarkManifest, Operation


CANONICAL_REPOSITORY_ROOT = Path(
    "/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness"
)


class PolicyError(PermissionError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class StageZeroPolicy:
    allowed_operations = frozenset(Operation)

    def authorize(self, manifest: BenchmarkManifest, operation: Operation) -> None:
        if manifest.stage != 0 or manifest.mode != "dry_run":
            raise PolicyError("stage_forbidden", "only Stage 0 dry-run mode is authorized")
        if operation not in self.allowed_operations or operation not in manifest.operations:
            raise PolicyError("operation_forbidden", f"operation is not authorized: {operation}")
        if manifest.output_root != CANONICAL_OUTPUT_ROOT:
            raise PolicyError("output_root_forbidden", "output root is outside policy")


class StageOnePolicy:
    allowed_operations = frozenset(Operation)

    def authorize(self, manifest: BenchmarkManifest, operation: Operation) -> None:
        if manifest.stage != 1 or manifest.mode != "live_route_comparison":
            raise PolicyError("stage_forbidden", "only the approved Stage 1 route comparison is authorized")
        if manifest.comparison_class != "route-overhead":
            raise PolicyError("comparison_forbidden", "only route-overhead is authorized")
        if operation not in self.allowed_operations or operation not in manifest.operations:
            raise PolicyError("operation_forbidden", f"operation is not authorized: {operation}")
        if manifest.output_root != CANONICAL_OUTPUT_ROOT:
            raise PolicyError("output_root_forbidden", "output root is outside policy")


class StageTwoPolicy:
    allowed_operations = frozenset(Operation)

    def authorize(self, manifest: BenchmarkManifest, operation: Operation) -> None:
        active_contracts = {
            (
                "3.1.0", "operator_route_probe",
                "optiq-operator-route-discovery", "3",
            ),
            (
                "3.3.0", "operator_inference_probe",
                "gemma-optiq-operator-route-smoke", "2",
            ),
        }
        contract = (
            manifest.schema_version, manifest.mode,
            manifest.comparison_class, manifest.runtime_profile_revision,
        )
        if manifest.stage != 2 or contract not in active_contracts:
            raise PolicyError("stage_forbidden", "Stage 2 contract is not active")
        if operation not in self.allowed_operations or operation not in manifest.operations:
            raise PolicyError("operation_forbidden", f"operation is not authorized: {operation}")
        if manifest.output_root != CANONICAL_OUTPUT_ROOT:
            raise PolicyError("output_root_forbidden", "output root is outside policy")
