from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.artifacts import (
    ArtifactBundle,
    ArtifactError,
    STAGE_TWO_INFERENCE_REQUIRED_FILES,
)
from local_model_runtime_evaluation.manifest import load_manifest


class ArtifactTest(unittest.TestCase):
    def test_stage_two_inference_schema_requires_complete_inference_bundle(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2-inference.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 15, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            self.assertEqual(bundle._required_files(), STAGE_TWO_INFERENCE_REQUIRED_FILES)
            bundle.write_json("preflight.json", {"ok": True})
            bundle.append_event({"state": "ready"})
            with self.assertRaisesRegex(ArtifactError, "incomplete"):
                bundle.finalize({"disposition": "PASS"})

    def test_bundle_detects_tampering(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-0.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 13, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            bundle.write_json("preflight.json", {"ok": True})
            bundle.write_json("inventory.json", {"commands": {}})
            bundle.append_event({"state": "queued"})
            bundle.finalize({"disposition": "STOPPED"})
            self.assertTrue(bundle.validate().valid)
            (bundle.path / "summary.json").write_text("{}\n")
            with self.assertRaises(ArtifactError):
                bundle.validate()

    def test_partial_finalize_checksums_existing_operator_evidence(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-2.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 14, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            bundle.write_json("preflight.json", {"ok": True})
            bundle.append_event({"state": "failed"})
            bundle.finalize_partial({"disposition": "STOPPED"})
            self.assertTrue(bundle.validate_partial().valid)

    def test_reseal_replaces_checksum_file_atomically(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-0.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 13, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            bundle.write_json("preflight.json", {"ok": True})
            bundle.write_json("inventory.json", {"commands": {}})
            bundle.append_event({"state": "queued"})
            bundle.finalize({"disposition": "STOPPED"})
            bundle.reseal_after_state_transition()
            self.assertFalse((bundle.path / "checksums.txt.tmp").exists())
            self.assertTrue(bundle.validate().valid)

    def test_reseal_ignores_a_stale_interrupted_checksum_temporary(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "valid-stage-0.json"
        manifest = load_manifest(fixture, now=datetime(2026, 7, 13, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            bundle.write_json("preflight.json", {"ok": True})
            bundle.write_json("inventory.json", {"commands": {}})
            bundle.append_event({"state": "queued"})
            bundle.finalize({"disposition": "STOPPED"})
            with (bundle.path / "lifecycle.jsonl").open("a", encoding="utf-8") as handle:
                handle.write('{"state":"cleaned"}\n')
            (bundle.path / "checksums.txt.tmp").write_text("interrupted replacement\n")

            bundle.reseal_after_state_transition()

            self.assertFalse((bundle.path / "checksums.txt.tmp").exists())
            self.assertTrue(bundle.validate().valid)


if __name__ == "__main__":
    unittest.main()
