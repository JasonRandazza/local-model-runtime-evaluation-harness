from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.manifest import ManifestError, validate_manifest


FIXTURE = Path(__file__).parent / "fixtures" / "valid-stage-1.json"


class StageOneManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(FIXTURE.read_text())
        self.now = datetime(2026, 7, 13, tzinfo=timezone.utc)

    def test_valid_stage_one_manifest_loads(self) -> None:
        manifest = validate_manifest(self.data, now=self.now)
        self.assertEqual(manifest.stage, 1)
        self.assertEqual(manifest.comparison_class, "route-overhead")
        self.assertEqual(manifest.model_profile_id, "vibethinker-3b-mlx-oq4")
        self.assertEqual(manifest.repetitions, 5)

    def test_rejects_route_drift_and_extra_properties(self) -> None:
        self.data["routes"]["direct"] = "http://example.com:8100/v1"
        with self.assertRaises(ManifestError):
            validate_manifest(self.data, now=self.now)
        self.data = json.loads(FIXTURE.read_text())
        self.data["command"] = "curl"
        with self.assertRaises(ManifestError):
            validate_manifest(self.data, now=self.now)

    def test_rejects_wrong_comparison_class_or_repetition_count(self) -> None:
        self.data["comparison_class"] = "native-best-stack"
        with self.assertRaises(ManifestError):
            validate_manifest(self.data, now=self.now)
        self.data = json.loads(FIXTURE.read_text())
        self.data["repetitions"] = 1
        with self.assertRaises(ManifestError):
            validate_manifest(self.data, now=self.now)


if __name__ == "__main__":
    unittest.main()
