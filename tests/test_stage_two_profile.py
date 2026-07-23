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

    def test_gemma_revision_one_profile_loads_with_draft_pins(self) -> None:
        profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
            "gemma-4-12b-optiq-4bit", "1"
        )
        gemma_model = Path(
            "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit"
        )
        self.assertEqual(profile.revision, "1")
        self.assertEqual(profile.coordinator_model_id, "gemma-4-12b-it-qat-jang_4m")
        self.assertEqual(profile.model_repository, "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit")
        self.assertEqual(profile.model_snapshot, gemma_model)
        self.assertEqual(
            profile.routed_model_id,
            "optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        )
        self.assertEqual(
            profile.rejected_local_model_ids,
            (
                "gemma-4-12b-optiq-4bit",
                "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
            ),
        )
        self.assertEqual(
            profile.artifact_hashes,
            {
                "config.json": (
                    "10c3765fec68c1cd13e6b67dd968468fa71c0e66f33b4c8003d9e7565f68b209"
                ),
                "optiq_metadata.json": (
                    "e64e0271ef661b18c1d6b54c395266681be08771aa3e11804c7a206ada32dddf"
                ),
                "model.safetensors.index.json": (
                    "62d43537384d711cd4af06295524cb92e1f6d3f3df7fdfbcbcb2628ea5d0f08d"
                ),
                "model-00001-of-00002.safetensors": (
                    "515896784d9237ed8545ee2668eb886f665b075abe8ae50dc70f10cf173763c1"
                ),
                "model-00002-of-00002.safetensors": (
                    "0bea2433d5812dbb20fddc75b4adaa2d33a964420209eabefef94579048b0457"
                ),
            },
        )
        self.assertEqual(profile.serve_arguments[2], str(gemma_model))
        self.assertEqual(profile.service_ownership, "operator")
        self.assertEqual(profile.provider_activation, "operator_reconnect_required")

    def test_gemma_revision_one_rejects_unprefixed_and_short_alias_as_routed_id(self) -> None:
        source = (
            self.root / "config" / "runtime-profiles" / "gemma-4-12b-optiq-4bit-r1.json"
        )
        self.assertTrue(source.is_file(), "gemma revision-1 profile must exist")
        base = json.loads(source.read_text())
        for routed_model_id in (
            "gemma-4-12b-optiq-4bit",
            "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        ):
            with self.subTest(routed_model_id=routed_model_id), tempfile.TemporaryDirectory() as temp:
                data = dict(base)
                data["routed_model_id"] = routed_model_id
                path = Path(temp) / "profile.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(RuntimeProfileError):
                    RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "1")

    def test_gemma_revision_two_pins_path_based_no_think_route(self) -> None:
        profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
            "gemma-4-12b-optiq-4bit", "2"
        )
        gemma_path = (
            "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit"
        )
        self.assertEqual(profile.revision, "2")
        self.assertEqual(
            profile.direct_model_identities[0],
            f"{gemma_path}:no-think",
        )
        self.assertEqual(
            profile.routed_model_id,
            f"optiq/{gemma_path}:no-think",
        )
        self.assertEqual(
            profile.rejected_local_model_ids,
            (
                "gemma-4-12b-optiq-4bit",
                "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
                "optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
                f"optiq/{gemma_path}",
            ),
        )
        self.assertEqual(profile.service_ownership, "operator")
        self.assertEqual(profile.provider_activation, "operator_reconnect_required")

    def test_gemma_revision_two_rejects_hub_shaped_and_bare_path_routed_ids(self) -> None:
        source = (
            self.root / "config" / "runtime-profiles" / "gemma-4-12b-optiq-4bit-r2.json"
        )
        base = json.loads(source.read_text())
        gemma_path = (
            "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit"
        )
        for routed_model_id in (
            "optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
            f"optiq/{gemma_path}",
            f"optiq/{gemma_path}:think",
        ):
            with self.subTest(routed_model_id=routed_model_id), tempfile.TemporaryDirectory() as temp:
                data = dict(base)
                data["routed_model_id"] = routed_model_id
                path = Path(temp) / "profile.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(RuntimeProfileError):
                    RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "2")

    def _gemma_revision_three_fixture(self) -> dict:
        source = (
            self.root / "config" / "runtime-profiles" / "gemma-4-12b-optiq-4bit-r2.json"
        )
        data = json.loads(source.read_text())
        data["revision"] = "3"
        data["runtime_version"] = "0.4.2"
        data["package_versions"] = {
            "mlx-optiq": "0.4.2",
            "mlx": "0.32.0",
            "mlx-lm": "0.31.3",
            "transformers": "5.12.1",
        }
        return data

    def _write_gemma_revision_three_fixture(self, temp: str, data: dict | None = None) -> None:
        payload = self._gemma_revision_three_fixture() if data is None else data
        Path(temp, "gemma-4-12b-optiq-4bit-r3.json").write_text(json.dumps(payload))

    def test_gemma_revision_three_profile_loads_with_optiq_042_pins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self._write_gemma_revision_three_fixture(temp)
            profile = RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "3")
            self.assertEqual(profile.revision, "3")
            self.assertEqual(profile.runtime_version, "0.4.2")
            self.assertEqual(profile.package_versions["mlx-optiq"], "0.4.2")

    def test_gemma_revision_three_rejects_runtime_version_033(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data = self._gemma_revision_three_fixture()
            data["runtime_version"] = "0.3.3"
            self._write_gemma_revision_three_fixture(temp, data)
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "3")

    def test_gemma_revision_three_rejects_wrong_mlx_optiq_package_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data = self._gemma_revision_three_fixture()
            data["package_versions"] = dict(data["package_versions"])
            data["package_versions"]["mlx-optiq"] = "0.3.3"
            self._write_gemma_revision_three_fixture(temp, data)
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "3")

    def test_gemma_revision_three_rejects_serve_argument_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data = self._gemma_revision_three_fixture()
            data["serve_arguments"] = list(data["serve_arguments"])
            data["serve_arguments"].append("--lab")
            self._write_gemma_revision_three_fixture(temp, data)
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "3")

    def test_gemma_registry_loads_revision_three_from_config(self) -> None:
        root = self.root / "config" / "runtime-profiles"
        registry = RuntimeProfileRegistry(root)
        self.assertEqual(registry.get("gemma-4-12b-optiq-4bit", "2").revision, "2")
        self.assertEqual(registry.get("gemma-4-12b-optiq-4bit", "2").runtime_version, "0.3.3")
        profile = registry.get("gemma-4-12b-optiq-4bit", "3")
        self.assertEqual(profile.revision, "3")
        self.assertEqual(profile.runtime_version, "0.4.2")
        self.assertEqual(profile.package_versions["mlx-optiq"], "0.4.2")

    def _gemma_revision_four_fixture(self) -> dict:
        data = self._gemma_revision_three_fixture()
        data["revision"] = "4"
        data["service_ownership"] = "harness"
        data["provider_activation"] = "verify_routed_id_only"
        return data

    def _write_gemma_revision_four_fixture(self, temp: str, data: dict | None = None) -> None:
        payload = self._gemma_revision_four_fixture() if data is None else data
        Path(temp, "gemma-4-12b-optiq-4bit-r4.json").write_text(json.dumps(payload))

    def test_gemma_revision_four_profile_loads_with_harness_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self._write_gemma_revision_four_fixture(temp)
            profile = RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "4")
            self.assertEqual(profile.revision, "4")
            self.assertEqual(profile.runtime_version, "0.4.2")
            self.assertEqual(profile.package_versions["mlx-optiq"], "0.4.2")
            self.assertEqual(profile.service_ownership, "harness")
            self.assertEqual(profile.provider_activation, "verify_routed_id_only")

    def test_gemma_revision_four_rejects_operator_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data = self._gemma_revision_four_fixture()
            data["service_ownership"] = "operator"
            data["provider_activation"] = "operator_reconnect_required"
            self._write_gemma_revision_four_fixture(temp, data)
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "4")

    def test_gemma_revision_three_still_requires_operator_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data = self._gemma_revision_three_fixture()
            data["service_ownership"] = "harness"
            data["provider_activation"] = "verify_routed_id_only"
            self._write_gemma_revision_three_fixture(temp, data)
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "3")

    def test_gemma_registry_loads_revision_four_from_config(self) -> None:
        root = self.root / "config" / "runtime-profiles"
        profile = RuntimeProfileRegistry(root).get("gemma-4-12b-optiq-4bit", "4")
        self.assertEqual(profile.revision, "4")
        self.assertEqual(profile.runtime_version, "0.4.2")
        self.assertEqual(profile.service_ownership, "harness")
        self.assertEqual(profile.provider_activation, "verify_routed_id_only")

    def _gemma_revision_five_fixture(self) -> dict:
        data = self._gemma_revision_four_fixture()
        data["revision"] = "5"
        data["provider_activation"] = "verify_routed_id_only_no_tap"
        return data

    def _write_gemma_revision_five_fixture(self, temp: str, data: dict | None = None) -> None:
        payload = self._gemma_revision_five_fixture() if data is None else data
        Path(temp, "gemma-4-12b-optiq-4bit-r5.json").write_text(json.dumps(payload))

    def test_gemma_revision_five_profile_loads_with_no_tap_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self._write_gemma_revision_five_fixture(temp)
            profile = RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "5")
            self.assertEqual(profile.revision, "5")
            self.assertEqual(profile.service_ownership, "harness")
            self.assertEqual(profile.provider_activation, "verify_routed_id_only_no_tap")
            self.assertEqual(profile.runtime_version, "0.4.2")

    def test_gemma_revision_five_rejects_legacy_verify_routed_id_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data = self._gemma_revision_five_fixture()
            data["provider_activation"] = "verify_routed_id_only"
            self._write_gemma_revision_five_fixture(temp, data)
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "5")

    def test_gemma_revision_four_still_rejects_no_tap_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data = self._gemma_revision_four_fixture()
            data["provider_activation"] = "verify_routed_id_only_no_tap"
            self._write_gemma_revision_four_fixture(temp, data)
            with self.assertRaises(RuntimeProfileError):
                RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "4")


if __name__ == "__main__":
    unittest.main()
