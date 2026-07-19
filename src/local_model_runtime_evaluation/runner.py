from __future__ import annotations

from datetime import datetime, timezone
import json
import signal
import threading
from pathlib import Path
from typing import Callable

from .artifacts import ArtifactBundle
from .inventory import collect_inventory
from .lifecycle import LifecycleStore
from .locking import RunLock
from .manifest import ManifestError, load_manifest
from .models import Disposition, Operation, RunStatus
from .policy import StageOnePolicy, StageTwoPolicy, StageZeroPolicy
from .stage_one import StageOneEngine
from .stage_two import StageTwoEngine, StageTwoError
from .stage_two_inference import StageTwoInferenceEngine
from .worker import WorkerLauncher


class RunnerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class StageZeroRunner:
    def __init__(
        self, repository_root: Path, output_root_override: Path | None = None,
        stage_one_engine_factory: Callable[[object, Path], StageOneEngine] | None = None,
        stage_two_engine_factory: Callable[[object, Path], StageTwoEngine | StageTwoInferenceEngine] | None = None,
        worker_launcher: WorkerLauncher | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.manifest_root = self.repository_root / "manifests"
        self.output_root_override = output_root_override
        self.stage_zero_policy = StageZeroPolicy()
        self.stage_one_policy = StageOnePolicy()
        self.stage_two_policy = StageTwoPolicy()
        self.stage_one_engine_factory = stage_one_engine_factory
        self.stage_two_engine_factory = stage_two_engine_factory
        self.worker_launcher = worker_launcher or WorkerLauncher(self.repository_root / "bin" / "lmre-stage0")

    def _manifest(self, run_id: str):
        matches = []
        for path in self.manifest_root.glob("*.json"):
            try:
                manifest = load_manifest(path)
            except ManifestError:
                continue
            if manifest.run_id == run_id:
                matches.append(manifest)
        if len(matches) != 1:
            raise RunnerError("manifest_not_found", f"one approved manifest is required for {run_id}")
        return matches[0]

    def _context(self, run_id: str, operation: Operation):
        manifest = self._manifest(run_id)
        policy = (
            self.stage_zero_policy if manifest.stage == 0
            else self.stage_one_policy if manifest.stage == 1
            else self.stage_two_policy
        )
        policy.authorize(manifest, operation)
        output_root = self.output_root_override or manifest.output_root
        return manifest, output_root, LifecycleStore(output_root), RunLock(output_root)

    def dispatch(self, operation: Operation, run_id: str | None = None) -> dict[str, object]:
        if operation is Operation.INVENTORY:
            return collect_inventory()
        if run_id is None:
            raise RunnerError("run_id_required", f"{operation.value} requires a run ID")
        manifest, output_root, lifecycle, lock = self._context(run_id, operation)

        if manifest.stage == 1:
            return self._dispatch_stage_one(operation, manifest, output_root, lifecycle, lock)
        if manifest.stage == 2:
            return self._dispatch_stage_two(operation, manifest, output_root, lifecycle, lock)

        if operation is Operation.PREFLIGHT:
            lock.acquire(run_id)
            bundle = ArtifactBundle.create(manifest, output_root)
            lifecycle.create(run_id)
            lifecycle.transition(run_id, RunStatus.PREFLIGHT, "manifest and policy validated")
            inventory = collect_inventory()
            bundle.write_json("inventory.json", inventory)
            bundle.write_json(
                "preflight.json",
                {
                    "ok": True,
                    "stage": 0,
                    "mode": "dry_run",
                    "network_calls_attempted": 0,
                    "harness_model_load_attempts": 0,
                    "harness_inference_request_attempts": 0,
                },
            )
            state = lifecycle.transition(run_id, RunStatus.READY, "Stage 0 simulation ready")
            return {
                "run_id": run_id,
                "state": state.status.value,
                "manifest_validation": "PASS",
                "manifest": {
                    "schema_version": manifest.schema_version,
                    "run_id": manifest.run_id,
                    "stage": manifest.stage,
                    "mode": manifest.mode,
                    "operations": [item.value for item in manifest.operations],
                    "output_root": str(manifest.output_root),
                    "approved_by": manifest.approved_by,
                    "approved_at": manifest.approved_at.isoformat(),
                    "expires_at": manifest.expires_at.isoformat(),
                    "simulation": dict(manifest.simulation),
                },
            }

        if operation is Operation.STATUS:
            state = lifecycle.read(run_id)
            return {"run_id": run_id, "state": state.status.value, "sequence": state.sequence}

        if operation is Operation.RUN_SCENARIO:
            state = lifecycle.transition(run_id, RunStatus.RUNNING, "simulation paused for cancellation")
            return {"run_id": run_id, "state": state.status.value, "awaiting_cancel": True}

        if operation is Operation.CANCEL:
            state = lifecycle.transition(run_id, RunStatus.CANCELLED, "operator-approved cancellation drill")
            return {"run_id": run_id, "state": state.status.value}

        if operation is Operation.CLEANUP:
            state = lifecycle.read(run_id)
            if state.status not in {RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.COMPLETE, RunStatus.CLEANED}:
                state = lifecycle.transition(run_id, RunStatus.CANCELLED, "cleanup requested before completion")
            state = lifecycle.transition(run_id, RunStatus.CLEANED, "idempotent Stage 0 cleanup")
            bundle = ArtifactBundle(output_root / run_id)
            summary = {
                "run_id": run_id,
                "stage": 0,
                "mode": "dry_run",
                "state": state.status.value,
                "disposition": Disposition.STOPPED.value,
                "harness_model_load_attempts": 0,
                "harness_inference_request_attempts": 0,
                "network_calls_attempted": 0,
                "finalized_at": datetime.now(timezone.utc).isoformat(),
            }
            if not (bundle.path / "checksums.txt").exists():
                bundle.finalize(summary)
            validation = bundle.validate()
            lock.release(run_id)
            return {
                "run_id": run_id,
                "state": state.status.value,
                "disposition": Disposition.STOPPED.value,
                "state_sequence": lifecycle.history(run_id),
                "artifact_directory": str(bundle.path),
                "artifact_validation": "PASS" if validation.valid else "FAIL",
                "required_artifacts_present": validation.valid,
                "checksum_validation": "PASS" if validation.valid else "FAIL",
                "artifacts": sorted([*validation.files, "checksums.txt"]),
                "harness_model_load_attempts": 0,
                "harness_inference_request_attempts": 0,
                "network_calls_attempted": 0,
            }

        raise RunnerError("operation_forbidden", f"unsupported operation: {operation.value}")

    def _stage_one_engine(self, manifest, output_root: Path) -> StageOneEngine:
        if self.stage_one_engine_factory is None:
            raise RunnerError("stage_one_not_prepared", "Stage 1 host dependencies are not prepared")
        return self.stage_one_engine_factory(manifest, output_root)

    def _dispatch_stage_one(self, operation, manifest, output_root, lifecycle, lock):
        run_id = manifest.run_id
        if operation is Operation.PREFLIGHT:
            lock.acquire(run_id)
            return self._stage_one_engine(manifest, output_root).preflight()
        if operation is Operation.STATUS:
            state = lifecycle.read(run_id)
            return {"run_id": run_id, "state": state.status.value, "sequence": state.sequence}
        if operation is Operation.RUN_SCENARIO:
            state = lifecycle.transition(run_id, RunStatus.RUNNING, "fixed Stage 1 worker starting")
            worker_path = output_root / run_id / "worker.json"
            pid = self.worker_launcher.launch(run_id, output_root / run_id / "worker.log")
            worker_path.write_text(json.dumps({"pid": pid}, sort_keys=True) + "\n", encoding="utf-8")
            return {"run_id": run_id, "state": state.status.value, "worker_pid": pid}
        if operation is Operation.CANCEL:
            try:
                worker = json.loads((output_root / run_id / "worker.json").read_text(encoding="utf-8"))
                self.worker_launcher.cancel(int(worker["pid"]), run_id)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
            state = lifecycle.transition(run_id, RunStatus.CANCELLED, "harness-owned worker cancellation requested")
            return {"run_id": run_id, "state": state.status.value}
        if operation is Operation.CLEANUP:
            state = lifecycle.read(run_id)
            if state.status is RunStatus.AWAITING_REVIEW:
                result = self._stage_one_engine(manifest, output_root).cleanup()
                lock.release(run_id)
                return result
            if state.status not in {RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.CLEANED}:
                state = lifecycle.transition(run_id, RunStatus.CANCELLED, "cleanup stopped incomplete Stage 1 run")
            if state.status is not RunStatus.CLEANED:
                state = lifecycle.transition(run_id, RunStatus.CLEANED, "partial Stage 1 evidence preserved")
            lock.release(run_id)
            return {
                "run_id": run_id, "state": state.status.value, "disposition": Disposition.STOPPED.value,
                "artifact_directory": str(output_root / run_id), "artifact_validation": "INCOMPLETE",
                "checksum_validation": "NOT_RUN", "manager_review_required": True,
            }
        raise RunnerError("operation_forbidden", f"unsupported Stage 1 operation: {operation.value}")

    def execute_stage_one_worker(self, run_id: str) -> dict[str, object]:
        manifest, output_root, lifecycle, _ = self._context(run_id, Operation.RUN_SCENARIO)
        try:
            return self._stage_one_engine(manifest, output_root).run(threading.Event())
        except Exception as error:
            try:
                lifecycle.transition(run_id, RunStatus.FAILED, "Stage 1 worker failed closed")
            except Exception:
                pass
            raise RunnerError("stage_one_worker_failed", str(error)) from error

    def _stage_two_engine(self, manifest, output_root: Path) -> StageTwoEngine | StageTwoInferenceEngine:
        if self.stage_two_engine_factory is None:
            raise RunnerError("stage_two_not_prepared", "Stage 2 host dependencies are not prepared")
        return self.stage_two_engine_factory(manifest, output_root)

    @staticmethod
    def _stage_two_preflight_recovery_path(output_root: Path, run_id: str) -> Path:
        return output_root / run_id / "preflight-recovery.json"

    def _record_stage_two_preflight_failure(self, manifest, output_root, lifecycle, error: Exception) -> None:
        run_id = manifest.run_id
        state = lifecycle.create(run_id)
        if state.status is not RunStatus.FAILED:
            lifecycle.transition(run_id, RunStatus.FAILED, "Stage 2 preflight failed closed")
        bundle = ArtifactBundle.create(manifest, output_root)
        bundle.write_json("preflight-recovery.json", {
            "run_id": run_id,
            "stage": 2,
            "mode": manifest.mode,
            "comparison_class": manifest.comparison_class,
            "state": RunStatus.FAILED.value,
            "failure_kind": getattr(error, "code", error.__class__.__name__),
            "service_lifecycle_actions": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
            "manager_review_required": True,
        })

    def _has_stage_two_preflight_recovery(self, output_root: Path, run_id: str) -> bool:
        try:
            payload = json.loads(
                self._stage_two_preflight_recovery_path(output_root, run_id).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return False
        return payload.get("run_id") == run_id and payload.get("stage") == 2

    def _cleanup_stage_two_preflight_failure(self, manifest, output_root, lifecycle) -> dict[str, object]:
        run_id = manifest.run_id
        bundle = ArtifactBundle(output_root / run_id)
        current = lifecycle.read(run_id)
        if current.status is RunStatus.CLEANED:
            try:
                summary = json.loads((bundle.path / "summary.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RunnerError("cleanup_failed", "cleaned preflight evidence is unavailable") from error
            state = current
        else:
            summary = {
                "run_id": run_id,
                "stage": 2,
                "mode": manifest.mode,
                "comparison_class": manifest.comparison_class,
                "state": RunStatus.CLEANED.value,
                "disposition": Disposition.STOPPED.value,
                "preflight_failure": "FAIL",
                "operator_cleanup_invoked": False,
                "service_lifecycle_actions": 0,
                "model_load_attempts": 0,
                "inference_request_attempts": 0,
                "http_post_attempts": 0,
                "manager_review_required": True,
            }
            bundle.finalize_partial(summary)
            state = lifecycle.transition(run_id, RunStatus.CLEANED, "failed Stage 2 preflight evidence cleaned")
        bundle.reseal_after_state_transition()
        validation = bundle.validate_partial()
        return {
            **summary,
            "state": state.status.value,
            "artifact_directory": str(bundle.path),
            "artifact_validation": "PASS" if validation.valid else "FAIL",
            "checksum_validation": "PASS" if validation.valid else "FAIL",
        }

    def _dispatch_stage_two(self, operation, manifest, output_root, lifecycle, lock):
        run_id = manifest.run_id
        if operation is Operation.PREFLIGHT:
            lock.acquire(run_id)
            try:
                return self._stage_two_engine(manifest, output_root).preflight()
            except Exception as error:
                self._record_stage_two_preflight_failure(manifest, output_root, lifecycle, error)
                raise RunnerError("stage_two_preflight_failed", str(error)) from error
        if operation is Operation.STATUS:
            state = lifecycle.read(run_id)
            return {"run_id": run_id, "state": state.status.value, "sequence": state.sequence}
        if operation is Operation.RUN_SCENARIO:
            state = lifecycle.transition(run_id, RunStatus.RUNNING, "fixed Stage 2 worker starting")
            worker_path = output_root / run_id / "worker.json"
            pid = self.worker_launcher.launch(run_id, output_root / run_id / "worker.log")
            worker_path.write_text(json.dumps({"pid": pid}, sort_keys=True) + "\n", encoding="utf-8")
            return {"run_id": run_id, "state": state.status.value, "worker_pid": pid}
        if operation is Operation.CANCEL:
            try:
                worker = json.loads((output_root / run_id / "worker.json").read_text(encoding="utf-8"))
                self.worker_launcher.cancel(int(worker["pid"]), run_id)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                raise RunnerError("cancellation_failed", "Stage 2 worker identity could not be verified") from error
            state = lifecycle.read(run_id)
            return {
                "run_id": run_id,
                "state": state.status.value,
                "cancellation_requested": True,
                "cleanup_pending": True,
            }
        if operation is Operation.CLEANUP:
            state = lifecycle.read(run_id)
            if (
                (manifest.schema_version, manifest.mode) == ("3.1.0", "operator_route_probe")
                and
                state.status in {RunStatus.FAILED, RunStatus.CLEANED}
                and self._has_stage_two_preflight_recovery(output_root, run_id)
            ):
                result = self._cleanup_stage_two_preflight_failure(manifest, output_root, lifecycle)
                lock.release(run_id)
                return result
            if state.status in {
                RunStatus.AWAITING_REVIEW, RunStatus.CANCELLED, RunStatus.FAILED,
                RunStatus.CLEANED,
            }:
                result = self._stage_two_engine(manifest, output_root).cleanup()
                lock.release(run_id)
                return result
            raise RunnerError("cleanup_pending", "Stage 2 worker must reach a terminal state before cleanup")
        raise RunnerError("operation_forbidden", f"unsupported Stage 2 operation: {operation.value}")

    def execute_stage_two_worker(self, run_id: str) -> dict[str, object]:
        manifest, output_root, lifecycle, _ = self._context(run_id, Operation.RUN_SCENARIO)
        cancel = threading.Event()
        previous = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, lambda _signum, _frame: cancel.set())
        try:
            return self._stage_two_engine(manifest, output_root).run(cancel)
        except StageTwoError as error:
            if error.code == "cancelled":
                raise RunnerError("stage_two_cancelled", str(error)) from error
            if lifecycle.read(run_id).status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
                try:
                    lifecycle.transition(run_id, RunStatus.FAILED, "Stage 2 worker failed closed")
                except Exception:
                    pass
            raise RunnerError("stage_two_worker_failed", str(error)) from error
        except Exception as error:
            try:
                lifecycle.transition(run_id, RunStatus.FAILED, "Stage 2 worker failed closed")
            except Exception:
                pass
            raise RunnerError("stage_two_worker_failed", str(error)) from error
        finally:
            signal.signal(signal.SIGTERM, previous)

    def validate_bundle(self, run_id: str) -> dict[str, object]:
        manifest = self._manifest(run_id)
        output_root = self.output_root_override or manifest.output_root
        result = ArtifactBundle(output_root / run_id).validate()
        return {"run_id": run_id, "valid": result.valid, "files": list(result.files)}
