from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.manifest import ManifestError, validate_manifest


FIXTURE = Path(__file__).parent / "fixtures" / "valid-stage-2.json"
INFERENCE_FIXTURE = Path(__file__).parent / "fixtures" / "valid-stage-2-inference.json"


class StageTwoManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(FIXTURE.read_text())
        self.now = datetime(2026, 7, 14, tzinfo=timezone.utc)

    def test_valid_stage_two_operator_route_manifest_loads(self) -> None:
        manifest = validate_manifest(self.data, now=self.now)
        self.assertEqual(manifest.stage, 2)
        self.assertEqual(manifest.schema_version, "3.1.0")
        self.assertEqual(manifest.mode, "operator_route_probe")
        self.assertEqual(manifest.comparison_class, "optiq-operator-route-discovery")
        self.assertEqual(manifest.runtime_profile_id, "vibethinker-3b-optiq-4bit")
        self.assertEqual(manifest.runtime_profile_revision, "3")
        self.assertEqual(
            manifest.limits,
            {"request_timeout_seconds": 10, "memory_stop_level": "critical"},
        )

    def test_valid_stage_two_inference_manifest_loads(self) -> None:
        data = json.loads(INFERENCE_FIXTURE.read_text())
        manifest = validate_manifest(data, now=self.now)
        self.assertEqual(manifest.schema_version, "3.2.0")
        self.assertEqual(manifest.mode, "operator_inference_probe")
        self.assertEqual(manifest.comparison_class, "optiq-operator-route-smoke")
        self.assertEqual(manifest.runtime_profile_revision, "3")
        self.assertEqual(manifest.suite_id, "optiq-route-smoke-v1")
        self.assertEqual(manifest.suite_revision, "1")
        self.assertEqual(manifest.repetitions, 1)
        self.assertEqual(manifest.route_order, "counterbalanced")
        self.assertEqual(
            manifest.limits,
            {
                "request_timeout_seconds": 120,
                "memory_stop_level": "warning",
                "maximum_in_flight_requests": 1,
                "total_request_limit": 8,
            },
        )

    def test_rejects_inference_contract_drift(self) -> None:
        cases = {
            "schema_version": "3.3.0",
            "mode": "operator_route_probe",
            "comparison_class": "optiq-operator-route-discovery",
            "runtime_profile_revision": "2",
            "suite_id": "route-overhead-v1",
            "suite_revision": "2",
            "repetitions": 2,
            "route_order": "direct-first",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                data = json.loads(INFERENCE_FIXTURE.read_text())
                data[field] = value
                with self.assertRaises(ManifestError):
                    validate_manifest(data, now=self.now)

    def test_rejects_inference_routes_and_limits_drift(self) -> None:
        cases = {
            ("routes", "direct"): "http://127.0.0.1:8100/v1",
            ("limits", "request_timeout_seconds"): 119,
            ("limits", "memory_stop_level"): "critical",
            ("limits", "maximum_in_flight_requests"): 2,
            ("limits", "total_request_limit"): 9,
        }
        for (section, field), value in cases.items():
            with self.subTest(section=section, field=field):
                data = json.loads(INFERENCE_FIXTURE.read_text())
                data[section][field] = value
                with self.assertRaises(ManifestError):
                    validate_manifest(data, now=self.now)

    def test_rejects_boolean_values_for_inference_numeric_constants(self) -> None:
        cases = [
            ("repetitions", None),
            ("limits", "maximum_in_flight_requests"),
            ("limits", "total_request_limit"),
        ]
        for case in cases:
            with self.subTest(case=case):
                data = json.loads(INFERENCE_FIXTURE.read_text())
                if case[0] == "repetitions":
                    data[case[0]] = True
                else:
                    data[case[0]][case[1]] = True
                with self.assertRaises(ManifestError):
                    validate_manifest(data, now=self.now)

    def test_rejects_inference_unknown_and_missing_properties(self) -> None:
        data = json.loads(INFERENCE_FIXTURE.read_text())
        data["unexpected"] = True
        with self.assertRaisesRegex(ManifestError, "unknown"):
            validate_manifest(data, now=self.now)
        data = json.loads(INFERENCE_FIXTURE.read_text())
        del data["suite_id"]
        with self.assertRaisesRegex(ManifestError, "missing"):
            validate_manifest(data, now=self.now)

    def test_preserves_historical_revision_two_lifecycle_validation(self) -> None:
        self.data["schema_version"] = "3.0.0"
        self.data["mode"] = "lifecycle_probe"
        self.data["comparison_class"] = "optiq-lifecycle-route-discovery"
        self.data["runtime_profile_revision"] = "2"
        self.data["limits"] = {
            "startup_timeout_seconds": 120,
            "shutdown_timeout_seconds": 30,
            "request_timeout_seconds": 10,
            "memory_stop_level": "critical",
        }
        manifest = validate_manifest(self.data, now=self.now)
        self.assertEqual(manifest.schema_version, "3.0.0")
        self.assertEqual(manifest.runtime_profile_revision, "2")

    def test_rejects_stage_two_route_and_limit_drift(self) -> None:
        self.data["routes"]["direct"] = "http://127.0.0.1:7860/v1"
        with self.assertRaises(ManifestError):
            validate_manifest(self.data, now=self.now)
        self.data = json.loads(FIXTURE.read_text())
        self.data["limits"]["startup_timeout_seconds"] = 600
        with self.assertRaises(ManifestError):
            validate_manifest(self.data, now=self.now)

    def test_rejects_generation_or_suite_authority(self) -> None:
        self.data["suite_id"] = "route-overhead-v1"
        with self.assertRaisesRegex(ManifestError, "unknown"):
            validate_manifest(self.data, now=self.now)


if __name__ == "__main__":
    unittest.main()
