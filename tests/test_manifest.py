from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.manifest import ManifestError, load_manifest, validate_manifest


FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


class ManifestTest(unittest.TestCase):
    def test_valid_stage_zero_manifest_loads(self) -> None:
        manifest = load_manifest(FIXTURES / "valid-stage-0.json", now=NOW)
        self.assertEqual(manifest.run_id, "stage0-20260713-001")
        self.assertEqual(manifest.stage, 0)

    def test_live_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ManifestError, "dry_run") as raised:
            load_manifest(FIXTURES / "invalid-live-mode.json", now=NOW)
        self.assertEqual(raised.exception.code, "live_mode_forbidden")

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(ManifestError) as raised:
            load_manifest(FIXTURES / "invalid-operation.json", now=NOW)
        self.assertEqual(raised.exception.code, "unknown_operation")

    def test_additional_property_is_rejected(self) -> None:
        data = json.loads((FIXTURES / "valid-stage-0.json").read_text())
        data["command"] = "whoami"
        with self.assertRaises(ManifestError) as raised:
            validate_manifest(data, now=NOW)
        self.assertEqual(raised.exception.code, "unknown_property")

    def test_expired_approval_is_rejected(self) -> None:
        data = json.loads((FIXTURES / "valid-stage-0.json").read_text())
        data["approved_at"] = "2026-07-01T00:00:00-04:00"
        data["expires_at"] = "2026-07-12T00:00:00-04:00"
        with self.assertRaises(ManifestError) as raised:
            validate_manifest(data, now=NOW)
        self.assertEqual(raised.exception.code, "approval_expired")

    def test_output_root_is_fixed(self) -> None:
        data = json.loads((FIXTURES / "valid-stage-0.json").read_text())
        data["output_root"] = "/tmp/elsewhere"
        with self.assertRaises(ManifestError) as raised:
            validate_manifest(data, now=NOW)
        self.assertEqual(raised.exception.code, "output_root_forbidden")

    def _benchmark_manifest(self) -> dict[str, object]:
        data = json.loads((FIXTURES / "valid-stage-2-inference-gemma.json").read_text())
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
        return data

    def test_valid_stage_two_harness_smoke_manifest_loads(self) -> None:
        now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        manifest = validate_manifest(
            json.loads((FIXTURES / "valid-stage-2-harness-smoke.json").read_text()),
            now=now,
        )
        self.assertEqual(manifest.schema_version, "3.5.0")
        self.assertEqual(manifest.mode, "harness_inference_probe")
        self.assertEqual(manifest.comparison_class, "gemma-optiq-042-harness-route-smoke")
        self.assertEqual(manifest.runtime_profile_revision, "4")
        self.assertEqual(manifest.suite_id, "gemma-optiq-042-harness-route-smoke-v1")

    def test_valid_stage_two_harness_benchmark_manifest_loads(self) -> None:
        now = datetime(2026, 7, 23, tzinfo=timezone.utc)
        manifest = validate_manifest(
            json.loads((FIXTURES / "valid-stage-2-harness-benchmark.json").read_text()),
            now=now,
        )
        self.assertEqual(manifest.schema_version, "3.6.0")
        self.assertEqual(manifest.mode, "harness_route_benchmark")
        self.assertEqual(manifest.comparison_class, "gemma-optiq-042-harness-route-benchmark")
        self.assertEqual(manifest.runtime_profile_revision, "5")
        self.assertEqual(manifest.suite_id, "gemma-optiq-042-harness-route-benchmark-v1")
        self.assertEqual(manifest.limits["total_request_limit"], 72)

    def test_valid_stage_two_benchmark_manifest_loads(self) -> None:
        now = datetime(2026, 7, 21, tzinfo=timezone.utc)
        manifest = validate_manifest(self._benchmark_manifest(), now=now)
        self.assertEqual(manifest.schema_version, "3.4.0")
        self.assertEqual(manifest.mode, "operator_route_benchmark")
        self.assertEqual(manifest.comparison_class, "gemma-optiq-operator-route-benchmark")
        self.assertEqual(manifest.suite_id, "gemma-optiq-route-benchmark-v1")
        self.assertEqual(manifest.limits["total_request_limit"], 72)

    def test_benchmark_manifest_rejects_smoke_limit(self) -> None:
        data = self._benchmark_manifest()
        data["limits"]["total_request_limit"] = 8
        with self.assertRaises(ManifestError) as raised:
            validate_manifest(data, now=datetime(2026, 7, 21, tzinfo=timezone.utc))
        self.assertEqual(raised.exception.code, "limits_invalid")

    def test_benchmark_manifest_rejects_smoke_suite(self) -> None:
        data = self._benchmark_manifest()
        data["suite_id"] = "gemma-optiq-route-smoke-v1"
        with self.assertRaises(ManifestError) as raised:
            validate_manifest(data, now=datetime(2026, 7, 21, tzinfo=timezone.utc))
        self.assertEqual(raised.exception.code, "suite_forbidden")


if __name__ == "__main__":
    unittest.main()
