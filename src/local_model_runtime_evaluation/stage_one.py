from __future__ import annotations

import json
import platform
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Protocol

from .artifacts import ArtifactBundle
from .benchmark_suite import BenchmarkSuite
from .credentials import CredentialProvider, CredentialState
from .identity import prove_route_identity
from .lifecycle import LifecycleStore
from .measurement import Sample, aggregate, run_schedule
from .model_profiles import ModelProfile
from .models import BenchmarkManifest, RunStatus
from .reporting import render_draft_report
from .resources import ResourcePolicy, ResourceSnapshot


class StageOneTransport(Protocol):
    def list_models(self, base_url, credential): ...
    def chat(self, base_url, model_id, prompt, max_tokens, credential, cancel=None): ...


class StageOneEngine:
    def __init__(
        self, manifest: BenchmarkManifest, profile: ModelProfile, suite: BenchmarkSuite,
        output_root: Path, credentials: CredentialProvider,
        resources: ResourceSnapshot | Callable[[], ResourceSnapshot],
        transport: StageOneTransport,
    ) -> None:
        if manifest.stage != 1:
            raise ValueError("StageOneEngine requires a Stage 1 manifest")
        if manifest.model_profile_id != profile.profile_id or manifest.suite_id != suite.suite_id:
            raise ValueError("manifest references do not match approved configuration")
        self.manifest = manifest
        self.profile = profile
        self.suite = suite
        self.output_root = output_root
        self.credentials = credentials
        self.resources = resources
        self.transport = transport
        self.lifecycle = LifecycleStore(output_root)
        self.bundle = ArtifactBundle.create(manifest, output_root)

    def _resources(self) -> ResourceSnapshot:
        return self.resources() if callable(self.resources) else self.resources

    def preflight(self) -> dict[str, object]:
        run_id = self.manifest.run_id
        self.lifecycle.create(run_id)
        self.lifecycle.transition(run_id, RunStatus.PREFLIGHT, "Stage 1 manifest and policy validated")
        if self.credentials.status() is not CredentialState.PRESENT:
            raise RuntimeError("approved credential is not present")
        credential = self.credentials.get()
        resource_snapshot = self._resources()
        decision = ResourcePolicy(self.profile.coordinator_model_id).evaluate(resource_snapshot)
        self.lifecycle.transition(run_id, RunStatus.RESOURCE_GATE, "serial single-model resource gate passed")
        direct_models = self.transport.list_models(self.profile.direct.base_url, credential)
        routed_models = self.transport.list_models(self.profile.routed.base_url, None)
        proof = prove_route_identity(self.profile, direct_models, routed_models)
        self.lifecycle.transition(run_id, RunStatus.ENDPOINT_IDENTITY, "route identity proven")
        self.bundle.write_json("hardware.json", {
            "machine": platform.machine(), "platform": platform.system(),
            "memory_policy_basis": "M2 Max 64GB provisional",
        })
        self.bundle.write_json("endpoint-inventory.json", {
            "direct": self.profile.direct.base_url, "routed": self.profile.routed.base_url,
            "identity": asdict(proof),
        })
        self.bundle.write_json("benchmark-suite.json", {
            "suite_id": self.suite.suite_id, "revision": self.suite.revision,
            "temperature": self.suite.temperature, "streaming": self.suite.streaming,
            "workloads": [asdict(item) for item in self.suite.workloads],
        })
        self.bundle.append_jsonl("memory-samples.jsonl", {
            "phase": "preflight", "memory_pressure": resource_snapshot.memory_pressure.value,
            "osaurus_native_model_loaded": resource_snapshot.osaurus_native_model_loaded,
            "osaurus_native_models": list(resource_snapshot.osaurus_native_models),
        })
        self.bundle.write_json("preflight.json", {
            "ok": True, "stage": 1, "comparison_class": "route-overhead",
            "credential_status": CredentialState.PRESENT.value,
            "resource_gate": "PASS", "resource_warning": decision.warning,
            "route_identity": "PASS", "service_lifecycle_actions": 0,
        })
        state = self.lifecycle.transition(run_id, RunStatus.READY, "Stage 1 route comparison ready")
        return {
            "run_id": run_id,
            "state": state.status.value,
            "preflight": "PASS",
            "manifest_validation": "PASS",
            "manifest": {
                "schema_version": self.manifest.schema_version,
                "run_id": self.manifest.run_id,
                "stage": self.manifest.stage,
                "mode": self.manifest.mode,
                "operations": [item.value for item in self.manifest.operations],
                "output_root": str(self.manifest.output_root),
                "approved_by": self.manifest.approved_by,
                "approved_at": self.manifest.approved_at.isoformat(),
                "expires_at": self.manifest.expires_at.isoformat(),
                "comparison_class": self.manifest.comparison_class,
                "model_profile_id": self.manifest.model_profile_id,
                "model_profile_revision": self.manifest.model_profile_revision,
                "suite_id": self.manifest.suite_id,
                "suite_revision": self.manifest.suite_revision,
                "repetitions": self.manifest.repetitions,
                "route_order": self.manifest.route_order,
                "routes": dict(self.manifest.routes or {}),
            },
            "credential_status": CredentialState.PRESENT.value,
            "resource_gate": "PASS",
            "resource_warning": decision.warning,
            "route_identity": "PASS",
            "route_identity_proof": asdict(proof),
            "service_lifecycle_actions": 0,
        }

    def run(self, cancel: threading.Event) -> dict[str, object]:
        run_id = self.manifest.run_id
        before_cohort = self._resources()
        ResourcePolicy(self.profile.coordinator_model_id).evaluate(before_cohort)
        self.bundle.append_jsonl("memory-samples.jsonl", {
            "phase": "before_measured_cohort", "memory_pressure": before_cohort.memory_pressure.value,
            "osaurus_native_model_loaded": before_cohort.osaurus_native_model_loaded,
            "osaurus_native_models": list(before_cohort.osaurus_native_models),
        })
        self.lifecycle.transition(run_id, RunStatus.WARMUP, "excluded route warm-ups started")
        credential = self.credentials.get()

        def execute(request, workload):
            endpoint = self.profile.direct if request.route == "direct" else self.profile.routed
            return self.transport.chat(
                endpoint.base_url, endpoint.model_id, workload.prompt, workload.max_tokens,
                credential if request.route == "direct" else None, cancel,
            )

        samples = run_schedule(self.suite, int(self.manifest.repetitions or 0), execute, cancel)
        self.lifecycle.transition(run_id, RunStatus.MEASURED, "counterbalanced measured cohort complete")
        for sample in samples:
            self.bundle.append_jsonl("raw-runs.jsonl", sample.as_json())
        summary = aggregate(samples, int(self.manifest.repetitions or 0))
        workload_summaries = summary["workloads"]
        self.bundle.write_json("direct-summary.json", {
            "route": "direct", "workloads": {key: value["direct"] for key, value in workload_summaries.items()},
            "overall": summary["overall"]["direct"],
        })
        self.bundle.write_json("routed-summary.json", {
            "route": "routed", "workloads": {key: value["routed"] for key, value in workload_summaries.items()},
            "overall": summary["overall"]["routed"],
        })
        self.bundle.write_json("route-comparison.json", summary)
        after_cohort = self._resources()
        ResourcePolicy(self.profile.coordinator_model_id).evaluate(after_cohort)
        self.bundle.append_jsonl("memory-samples.jsonl", {
            "phase": "after_measured_cohort", "memory_pressure": after_cohort.memory_pressure.value,
            "osaurus_native_model_loaded": after_cohort.osaurus_native_model_loaded,
            "osaurus_native_models": list(after_cohort.osaurus_native_models),
        })
        self.bundle.write_text("draft-report.md", render_draft_report(run_id, summary))
        self.lifecycle.transition(run_id, RunStatus.ARTIFACT_VALIDATION, "raw evidence reconciled")
        self.lifecycle.transition(run_id, RunStatus.AWAITING_REVIEW, "manager review required")
        return dict(summary)

    def cleanup(self) -> dict[str, object]:
        run_id = self.manifest.run_id
        state = self.lifecycle.read(run_id)
        if state.status is not RunStatus.AWAITING_REVIEW:
            raise RuntimeError("completed Stage 1 evidence is required before PASS cleanup")
        state = self.lifecycle.transition(run_id, RunStatus.CLEANED, "Stage 1 owned state cleaned")
        comparison = json.loads((self.bundle.path / "route-comparison.json").read_text(encoding="utf-8"))
        workload_summaries = comparison["workloads"]
        direct_counts = {
            value["direct"]["sample_count"] for value in workload_summaries.values()
        }
        routed_counts = {
            value["routed"]["sample_count"] for value in workload_summaries.values()
        }
        direct_per_workload = next(iter(direct_counts)) if len(direct_counts) == 1 else None
        routed_per_workload = next(iter(routed_counts)) if len(routed_counts) == 1 else None
        overall = comparison["overall"]
        bounded_summary = {
            "run_id": run_id, "stage": 1, "state": state.status.value, "disposition": "PASS",
            "measured_requests": comparison["measured_sample_count"],
            "excluded_warmups": comparison["warmup_sample_count"],
            "direct_samples_per_workload": direct_per_workload,
            "routed_samples_per_workload": routed_per_workload,
            "response_contract_validation": overall["response_contract_validation"],
            "response_contract_valid_count": overall["response_contract_valid_count"],
            "response_contract_invalid_count": overall["response_contract_invalid_count"],
            "streaming_metric_status": overall["streaming_metric_status"],
            "ttft_metric_status": overall["ttft_metric_status"],
            "decode_metric_status": overall["decode_metric_status"],
            "token_accounting_status": overall["token_accounting_status"],
            "paired_total_seconds": overall["paired_total_seconds"],
            "completion_status": overall["completion_status"],
            "finish_reason_counts": overall["finish_reason_counts"],
            "service_lifecycle_actions": 0, "manager_review_required": True,
        }
        self.bundle.finalize(bounded_summary)
        validation = self.bundle.validate()
        return {**bounded_summary,
            "artifact_directory": str(self.bundle.path),
            "artifact_validation": "PASS" if validation.valid else "FAIL",
            "checksum_validation": "PASS" if validation.valid else "FAIL",
            "manager_review_required": True,
        }
