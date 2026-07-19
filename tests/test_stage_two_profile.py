from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfileError, RuntimeProfileRegistry


class StageTwoRuntimeProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]

    def test_pinned_optiq_profile_has_exact_api_only_identity(self) -> None:
        profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
            "vibethinker-3b-optiq-4bit", "2"
        )
        self.assertEqual(profile.runtime_version, "0.3.3")
        self.assertEqual(profile.coordinator_model_id, "gemma-4-12b-it-qat-jang_4m")
        self.assertEqual(profile.model_revision, "94bce93443d4f62946ae89261f62e0ecdbb1ef1e")
        self.assertIn("mlx-community/VibeThinker-3B-OptiQ-4bit", profile.direct_model_identities)
        self.assertEqual(
            profile.routed_model_id,
            "mlx-community/VibeThinker-3B-OptiQ-4bit",
        )
        self.assertEqual(
            profile.rejected_local_model_ids,
            ("vibethinker-3b-optiq-4bit",),
        )
        self.assertFalse(hasattr(profile, "routed_prefix_hypothesis"))
        self.assertIn("--no-anthropic", profile.serve_arguments)
        self.assertIn("--no-responses", profile.serve_arguments)
        self.assertIn("--single-model", profile.serve_arguments)
        self.assertNotIn("lab", profile.serve_arguments)
        self.assertEqual(set(profile.artifact_hashes), {
            "model.safetensors", "config.json", "optiq_metadata.json", "model.safetensors.index.json"
        })

    def test_revision_three_profile_uses_operator_owned_prefixed_route(self) -> None:
        profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
            "vibethinker-3b-optiq-4bit", "3"
        )
        self.assertEqual(profile.service_ownership, "operator")
        self.assertEqual(profile.provider_activation, "operator_reconnect_required")
        self.assertEqual(
            profile.routed_model_id,
            "optiq/mlx-community/VibeThinker-3B-OptiQ-4bit",
        )
        self.assertEqual(
            profile.rejected_local_model_ids,
            (
                "vibethinker-3b-optiq-4bit",
                "mlx-community/VibeThinker-3B-OptiQ-4bit",
            ),
        )

    def test_registry_selects_the_requested_revision_when_both_are_present(self) -> None:
        root = self.root / "config" / "runtime-profiles"
        registry = RuntimeProfileRegistry(root)
        self.assertEqual(registry.get("vibethinker-3b-optiq-4bit", "2").revision, "2")
        self.assertEqual(registry.get("vibethinker-3b-optiq-4bit", "3").revision, "3")

    def test_revision_three_rejects_raw_and_local_route_ids(self) -> None:
        source = self.root / "config" / "runtime-profiles" / "vibethinker-3b-optiq-4bit-r3.json"
        base = json.loads(source.read_text())
        for routed_model_id in (
            "vibethinker-3b-optiq-4bit",
            "mlx-community/VibeThinker-3B-OptiQ-4bit",
        ):
            with self.subTest(routed_model_id=routed_model_id), tempfile.TemporaryDirectory() as temp:
                data = dict(base)
                data["routed_model_id"] = routed_model_id
                path = Path(temp) / "profile.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(RuntimeProfileError):
                    RuntimeProfileRegistry(Path(temp)).get("vibethinker-3b-optiq-4bit", "3")

    def test_registry_rejects_unknown_fields_and_mutable_model_path(self) -> None:
        source = self.root / "config" / "runtime-profiles" / "vibethinker-3b-optiq-4bit.json"
        data = json.loads(source.read_text())
        data["shell_command"] = "optiq lab"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profile.json"
            path.write_text(json.dumps(data))
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("vibethinker-3b-optiq-4bit", "2")

    def test_registry_rejects_route_identity_and_revision_drift(self) -> None:
        source = self.root / "config" / "runtime-profiles" / "vibethinker-3b-optiq-4bit.json"
        base = json.loads(source.read_text())
        mutations = (
            {"routed_model_id": "optiq/VibeThinker-3B-OptiQ-4bit"},
            {"rejected_local_model_ids": []},
            {"revision": "1"},
            {"routed_prefix_hypothesis": "optiq/"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                data = dict(base)
                data.update(mutation)
                path = Path(temp) / "profile.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(RuntimeProfileError):
                    RuntimeProfileRegistry(Path(temp)).get("vibethinker-3b-optiq-4bit", "2")


if __name__ == "__main__":
    unittest.main()
