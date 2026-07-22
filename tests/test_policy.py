from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.adapters.base import LiveExecutionDisabled
from local_model_runtime_evaluation.adapters.openai_compatible import OpenAICompatibleAdapter
from local_model_runtime_evaluation.adapters.optiq import OptiQAdapter
from local_model_runtime_evaluation.adapters.osaurus import OsaurusAdapter
from local_model_runtime_evaluation.manifest import ManifestError, load_manifest, validate_manifest
from local_model_runtime_evaluation.models import Operation
from local_model_runtime_evaluation.policy import PolicyError, StageTwoPolicy, StageZeroPolicy


class PolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-0.json"
        self.manifest = load_manifest(fixture, now=datetime(2026, 7, 13, tzinfo=timezone.utc))

    def test_six_operations_are_authorized(self) -> None:
        policy = StageZeroPolicy()
        for operation in Operation:
            policy.authorize(self.manifest, operation)

    def test_runtime_adapters_are_disabled(self) -> None:
        for adapter in (OsaurusAdapter(), OpenAICompatibleAdapter(), OptiQAdapter()):
            with self.assertRaises(LiveExecutionDisabled):
                adapter.execute()

    def test_revision_three_operator_route_manifest_authorizes_all_six_operations(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 14, tzinfo=timezone.utc))
        policy = StageTwoPolicy()
        for operation in Operation:
            policy.authorize(manifest, operation)

    def test_gemma_inference_manifest_authorizes_all_six_operations(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 20, tzinfo=timezone.utc))
        policy = StageTwoPolicy()
        for operation in Operation:
            policy.authorize(manifest, operation)

    def test_historical_inference_manifest_is_not_authorized(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2-inference.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 15, tzinfo=timezone.utc))
        with self.assertRaises(PolicyError):
            StageTwoPolicy().authorize(manifest, Operation.INVENTORY)

    def test_revision_two_lifecycle_contract_is_not_authorized(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2.json"
        manifest_data = json.loads(fixture.read_text())
        manifest_data["mode"] = "lifecycle_probe"
        manifest_data["comparison_class"] = "optiq-lifecycle-route-discovery"
        manifest_data["runtime_profile_revision"] = "2"
        manifest_data["limits"] = {
            "startup_timeout_seconds": 120,
            "shutdown_timeout_seconds": 30,
            "request_timeout_seconds": 10,
            "memory_stop_level": "critical",
        }
        manifest_data["schema_version"] = "3.0.0"
        manifest = validate_manifest(manifest_data, now=datetime(2026, 7, 14, tzinfo=timezone.utc))
        with self.assertRaises(PolicyError):
            StageTwoPolicy().authorize(manifest, Operation.INVENTORY)

    def test_active_operator_route_policy_requires_schema_3_1(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 14, tzinfo=timezone.utc))
        with self.assertRaises(PolicyError):
            StageTwoPolicy().authorize(replace(manifest, schema_version="3.0.0"), Operation.INVENTORY)

    def test_benchmark_manifest_authorizes_all_six_operations(self) -> None:
        data = json.loads((
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json"
        ).read_text())
        data.update({
            "schema_version": "3.4.0",
            "mode": "operator_route_benchmark",
            "comparison_class": "gemma-optiq-operator-route-benchmark",
            "suite_id": "gemma-optiq-route-benchmark-v1",
            "limits": {
                "request_timeout_seconds": 120,
                "memory_stop_level": "warning",
                "maximum_in_flight_requests": 1,
                "total_request_limit": 72,
            },
        })
        manifest = validate_manifest(data, now=datetime(2026, 7, 21, tzinfo=timezone.utc))
        policy = StageTwoPolicy()
        for operation in Operation:
            policy.authorize(manifest, operation)

    def test_gemma_live_authorizing_schemas_reject_profile_revision_three(self) -> None:
        smoke = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json",
            now=datetime(2026, 7, 20, tzinfo=timezone.utc),
        )
        benchmark_data = json.loads((
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json"
        ).read_text())
        benchmark_data.update({
            "schema_version": "3.4.0",
            "mode": "operator_route_benchmark",
            "comparison_class": "gemma-optiq-operator-route-benchmark",
            "suite_id": "gemma-optiq-route-benchmark-v1",
            "limits": {
                "request_timeout_seconds": 120,
                "memory_stop_level": "warning",
                "maximum_in_flight_requests": 1,
                "total_request_limit": 72,
            },
        })
        benchmark = validate_manifest(benchmark_data, now=datetime(2026, 7, 21, tzinfo=timezone.utc))
        policy = StageTwoPolicy()
        for manifest in (
            replace(smoke, runtime_profile_revision="3"),
            replace(benchmark, runtime_profile_revision="3"),
        ):
            with self.subTest(schema_version=manifest.schema_version):
                with self.assertRaises(PolicyError) as ctx:
                    policy.authorize(manifest, Operation.INVENTORY)
                self.assertEqual(ctx.exception.code, "stage_forbidden")

    def test_harness_smoke_manifest_authorizes_all_six_operations(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2-harness-smoke.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 22, tzinfo=timezone.utc))
        policy = StageTwoPolicy()
        for operation in Operation:
            policy.authorize(manifest, operation)

    def test_harness_smoke_rejects_operator_comparison_class(self) -> None:
        data = json.loads((
            Path(__file__).parent / "fixtures" / "valid-stage-2-harness-smoke.json"
        ).read_text())
        data["comparison_class"] = "gemma-optiq-operator-route-smoke"
        with self.assertRaises(ManifestError):
            validate_manifest(data, now=datetime(2026, 7, 22, tzinfo=timezone.utc))

    def test_harness_smoke_rejects_profile_revision_two_or_three(self) -> None:
        for revision in ("2", "3"):
            with self.subTest(revision=revision):
                data = json.loads((
                    Path(__file__).parent / "fixtures" / "valid-stage-2-harness-smoke.json"
                ).read_text())
                data["runtime_profile_revision"] = revision
                with self.assertRaises(ManifestError):
                    validate_manifest(data, now=datetime(2026, 7, 22, tzinfo=timezone.utc))

    def test_operator_smoke_still_rejects_harness_comparison_class(self) -> None:
        data = json.loads((
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json"
        ).read_text())
        data["comparison_class"] = "gemma-optiq-042-harness-route-smoke"
        with self.assertRaises(ManifestError):
            validate_manifest(data, now=datetime(2026, 7, 20, tzinfo=timezone.utc))

    def test_benchmark_manifest_rejects_smoke_suite_under_policy(self) -> None:
        data = json.loads((
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json"
        ).read_text())
        data.update({
            "schema_version": "3.4.0",
            "mode": "operator_route_benchmark",
            "comparison_class": "gemma-optiq-operator-route-benchmark",
            "suite_id": "gemma-optiq-route-smoke-v1",
            "limits": {
                "request_timeout_seconds": 120,
                "memory_stop_level": "warning",
                "maximum_in_flight_requests": 1,
                "total_request_limit": 72,
            },
        })
        with self.assertRaises(ManifestError):
            validate_manifest(data, now=datetime(2026, 7, 21, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
