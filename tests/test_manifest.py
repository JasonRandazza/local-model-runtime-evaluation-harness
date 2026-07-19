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


if __name__ == "__main__":
    unittest.main()
