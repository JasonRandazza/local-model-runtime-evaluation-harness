from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.model_profiles import ModelProfileError, ModelProfileRegistry


PROFILE = """{
  "schema_version": "1.0.0",
  "profile_id": "vibethinker-3b-mlx-oq4",
  "revision": "2",
  "approved": true,
  "runtime_owner": "omlx",
  "comparison_classes": ["route-overhead"],
  "coordinator_model_id": "gemma-4-12b-it-qat-jang_4m",
  "direct": {"base_url": "http://127.0.0.1:8100/v1", "model_id": "VibeThinker-3B-MLX-oQ4"},
  "routed": {"base_url": "http://127.0.0.1:1337/v1", "model_id": "VibeThinker-3B-MLX-oQ4"},
  "tokenizer": {"kind": "api-usage-verified", "identity": "VibeThinker-3B-MLX-oQ4"},
  "suite_id": "route-overhead-v1",
  "credential_ref": "local.jrazz.lmre.omlx",
  "limits": {"request_timeout_seconds": 120, "memory_stop_level": "critical"}
}"""


class ModelProfileRegistryTest(unittest.TestCase):
    def test_loads_only_approved_revision_matched_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profile.json").write_text(PROFILE)
            profile = ModelProfileRegistry(root).get("vibethinker-3b-mlx-oq4", "2")
            self.assertEqual(profile.runtime_owner, "omlx")
            self.assertEqual(profile.coordinator_model_id, "gemma-4-12b-it-qat-jang_4m")
            self.assertEqual(profile.direct.port, 8100)
            self.assertEqual(profile.routed.port, 1337)

    def test_rejects_unknown_profile_and_revision_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profile.json").write_text(PROFILE)
            registry = ModelProfileRegistry(root)
            with self.assertRaises(ModelProfileError):
                registry.get("other", "2")
            with self.assertRaises(ModelProfileError):
                registry.get("vibethinker-3b-mlx-oq4", "1")

    def test_rejects_non_loopback_and_disabled_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profile.json").write_text(
                PROFILE.replace('"approved": true', '"approved": false').replace(
                    "127.0.0.1:8100", "example.com:8100"
                )
            )
            with self.assertRaises(ModelProfileError):
                ModelProfileRegistry(root).get("vibethinker-3b-mlx-oq4", "2")


if __name__ == "__main__":
    unittest.main()
