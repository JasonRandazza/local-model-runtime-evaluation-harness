from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.artifacts import ArtifactBundle, ArtifactError, STAGE_ONE_REQUIRED_FILES
from local_model_runtime_evaluation.manifest import load_manifest


class StageOneArtifactTest(unittest.TestCase):
    def test_stage_one_bundle_requires_and_checksums_complete_evidence(self) -> None:
        manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-1.json",
            now=datetime(2026, 7, 13, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            for name in STAGE_ONE_REQUIRED_FILES - {"manifest.json", "raw-runs.jsonl", "memory-samples.jsonl", "lifecycle.jsonl", "draft-report.md", "summary.json"}:
                bundle.write_json(name, {"ok": True})
            bundle.append_jsonl("raw-runs.jsonl", {"route": "direct"})
            bundle.append_jsonl("memory-samples.jsonl", {"memory_pressure": "normal"})
            bundle.append_event({"status": "queued"})
            bundle.write_text("draft-report.md", "# Draft\n")
            bundle.finalize({"disposition": "PASS"})
            self.assertTrue(bundle.validate().valid)
            self.assertTrue(STAGE_ONE_REQUIRED_FILES.issubset(set(bundle.validate().files)))
            (bundle.path / "route-comparison.json").write_text("{}\n")
            with self.assertRaises(ArtifactError):
                bundle.validate()


if __name__ == "__main__":
    unittest.main()
