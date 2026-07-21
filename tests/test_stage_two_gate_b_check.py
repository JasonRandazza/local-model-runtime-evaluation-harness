from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from local_model_runtime_evaluation.stage_two import HostValidation, ModelDescriptor
from local_model_runtime_evaluation.stage_two_host import ProcessSnapshot
from local_model_runtime_evaluation import stage_two_gate_b_check as gate_b_mod
from local_model_runtime_evaluation.stage_two_gate_b_check import (
    build_gate_b_report,
    collect_plugin_state,
    collect_static_result,
    load_authorized_manifest,
    parse_active_plugin_version,
)
from local_model_runtime_evaluation.stage_two_profiles import (
    RuntimeProfile,
    RuntimeProfileRegistry,
)


class FakeValidator:
    def validate(self) -> HostValidation:
        return HostValidation(
            runtime_identity={"version": "0.3.3", "packages": {"mlx-optiq": "0.3.3"}},
            artifact_identity={"revision": "abc", "hashes": {"model": "hash"}},
            provider_identity={
                "provider_id": "Optiq", "enabled": True,
                "custom_header_count": 0, "secret_header_key_count": 0,
            },
        )


class FakeProcessBackend:
    def __init__(self, command: tuple[str, ...]) -> None:
        self.snapshot = ProcessSnapshot(4242, 4000, 4242, "start", command)
        self.extra: ProcessSnapshot | None = None

    def port_is_free(self) -> bool:
        return False

    def listener_process_ids(self) -> tuple[int, ...]:
        return (4242,)

    def optiq_processes(self) -> tuple[object, ...]:
        return (self.snapshot,) if self.extra is None else (self.snapshot, self.extra)

    def describe(self, pid: int) -> ProcessSnapshot | None:
        return self.snapshot if pid == 4242 else None


class FakeTransport:
    def health(self, base_url: str) -> dict[str, object]:
        if ":8080" in base_url:
            return {"status": "ok"}
        return {
            "status": "healthy", "loaded": ["gemma"],
            "resident_models": [], "current_model": "gemma",
        }

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        if ":8080" in base_url:
            return (ModelDescriptor("repo"),)
        return (ModelDescriptor("optiq/repo"),)


class FakeResourceProbe:
    def free_memory_percent(self) -> int:
        return 80


class StageTwoGateBCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.static = {
            "runtime_profile_id": "gemma-4-12b-optiq-4bit",
            "runtime_profile_revision": "2",
            "runtime_identity": "PASS",
            "artifact_identity": "PASS",
            "provider_identity": "PASS",
            "resource_gate": "PASS",
            "port_8080_free": False,
            "optiq_process_count": 1,
            "operator_service_identity": "PASS",
            "route_identity": "PASS",
            "custom_header_count": 0,
            "secret_header_key_count": 0,
            "model_load_attempts": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
            "service_lifecycle_actions": 0,
        }

    def test_gate_b_pins_gemma_profile_and_routed_id(self) -> None:
        self.assertEqual(gate_b_mod._PROFILE_ID, "gemma-4-12b-optiq-4bit")
        self.assertEqual(gate_b_mod._PROFILE_REVISION, "2")
        self.assertEqual(
            gate_b_mod._ROUTED_MODEL_ID,
            "optiq//Users/jrazz/.cache/huggingface/hub/"
            "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think",
        )

    def test_reports_ready_for_plugin_install_before_upgrade(self) -> None:
        result = build_gate_b_report(
            static_result=self.static, installed_version="0.2.0",
            packaged_sha256="new", installed_sha256=None, manifest=None,
        )
        self.assertEqual(result["overall"], "READY_FOR_PLUGIN_INSTALL")
        self.assertFalse(result["checks"]["plugin_version"])

    def test_reports_ready_for_manifest_after_matching_plugin(self) -> None:
        result = build_gate_b_report(
            static_result=self.static, installed_version="0.3.0",
            packaged_sha256="same", installed_sha256="same", manifest=None,
        )
        self.assertEqual(result["overall"], "READY_FOR_MANIFEST_AUTHORIZATION")
        self.assertEqual(result["runtime_profile_id"], "gemma-4-12b-optiq-4bit")
        self.assertEqual(result["runtime_profile_revision"], "2")

    def test_stops_on_provider_or_zero_activity_failure(self) -> None:
        static = dict(self.static)
        static["custom_header_count"] = 1
        result = build_gate_b_report(
            static_result=static, installed_version="0.3.0",
            packaged_sha256="same", installed_sha256="same", manifest=None,
        )
        self.assertEqual(result["overall"], "STOPPED")
        self.assertTrue(result["manager_review_required"])

    def test_collects_read_only_static_evidence_with_zero_activity(self) -> None:
        profile = RuntimeProfile(
            profile_id="profile", revision="3", runtime_executable=Path("/optiq"),
            runtime_version="0.3.3", coordinator_model_id="gemma",
            package_versions={"mlx-optiq": "0.3.3"}, model_repository="repo",
            model_revision="abc", model_snapshot=Path("/model"),
            artifact_hashes={"model": "hash"}, serve_arguments=("serve", "--model", "/model"),
            direct_base_url="http://127.0.0.1:8080/v1",
            routed_base_url="http://127.0.0.1:1337/v1",
            direct_model_identities=("repo",), osaurus_provider_id="Optiq",
            routed_model_id="optiq/repo",
            rejected_local_model_ids=("local", "repo"),
            service_ownership="operator", provider_activation="operator_reconnect_required",
        )
        command = (str(profile.runtime_executable), *profile.serve_arguments)

        result = collect_static_result(
            profile=profile, validator=FakeValidator(),
            process_backend=FakeProcessBackend(command), transport=FakeTransport(),
            resource_probe=FakeResourceProbe(),
        )

        self.assertEqual(result["runtime_identity"], "PASS")
        self.assertEqual(result["runtime_profile_id"], "profile")
        self.assertEqual(result["runtime_profile_revision"], "3")
        self.assertEqual(result["artifact_identity"], "PASS")
        self.assertEqual(result["provider_identity"], "PASS")
        self.assertEqual(result["resource_gate"], "PASS")
        self.assertEqual(result["coordinator_model_id"], "gemma")
        self.assertEqual(result["model_load_attempts"], 0)
        self.assertEqual(result["inference_request_attempts"], 0)
        self.assertEqual(result["http_post_attempts"], 0)
        self.assertEqual(result["service_lifecycle_actions"], 0)
        self.assertEqual(result["operator_service_identity"], "PASS")
        self.assertEqual(result["route_identity"], "PASS")
        self.assertFalse(result["port_8080_free"])

    def test_dry_gate_b_static_evidence_accepts_gemma_profile_pins(self) -> None:
        root = Path(__file__).parents[1]
        profile = RuntimeProfileRegistry(root / "config" / "runtime-profiles").get(
            "gemma-4-12b-optiq-4bit", "2",
        )
        self.assertEqual(profile.routed_model_id, gate_b_mod._ROUTED_MODEL_ID)

        class GemmaValidator(FakeValidator):
            def validate(self) -> HostValidation:
                return HostValidation(
                    runtime_identity={
                        "version": profile.runtime_version,
                        "packages": dict(profile.package_versions),
                    },
                    artifact_identity={
                        "revision": profile.model_revision,
                        "hashes": dict(profile.artifact_hashes),
                    },
                    provider_identity={
                        "provider_id": profile.osaurus_provider_id,
                        "enabled": True,
                        "custom_header_count": 0,
                        "secret_header_key_count": 0,
                    },
                )

        class GemmaTransport(FakeTransport):
            def health(self, base_url: str) -> dict[str, object]:
                if ":8080" in base_url:
                    return {"status": "ok"}
                return {
                    "status": "healthy",
                    "loaded": [profile.coordinator_model_id],
                    "resident_models": [],
                    "current_model": profile.coordinator_model_id,
                }

            def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
                if ":8080" in base_url:
                    return (ModelDescriptor(profile.direct_model_identities[0]),)
                return (ModelDescriptor(profile.routed_model_id),)

        command = (str(profile.runtime_executable), *profile.serve_arguments)
        result = collect_static_result(
            profile=profile,
            validator=GemmaValidator(),
            process_backend=FakeProcessBackend(command),
            transport=GemmaTransport(),
            resource_probe=FakeResourceProbe(),
        )

        self.assertEqual(result["runtime_profile_id"], "gemma-4-12b-optiq-4bit")
        self.assertEqual(result["runtime_profile_revision"], "2")
        self.assertEqual(result["route_identity"], "PASS")
        self.assertEqual(result["coordinator_model_id"], "gemma-4-12b-it-qat-jang_4m")
        self.assertEqual(result["model_load_attempts"], 0)
        self.assertEqual(result["http_post_attempts"], 0)
        self.assertEqual(result["service_lifecycle_actions"], 0)

    def test_rejects_routed_health_the_worker_would_reject(self) -> None:
        profile = RuntimeProfile(
            profile_id="profile", revision="3", runtime_executable=Path("/optiq"),
            runtime_version="0.3.3", coordinator_model_id="gemma",
            package_versions={"mlx-optiq": "0.3.3"}, model_repository="repo",
            model_revision="abc", model_snapshot=Path("/model"),
            artifact_hashes={"model": "hash"}, serve_arguments=("serve", "--model", "/model"),
            direct_base_url="http://127.0.0.1:8080/v1",
            routed_base_url="http://127.0.0.1:1337/v1",
            direct_model_identities=("repo",), osaurus_provider_id="Optiq",
            routed_model_id="optiq/repo", rejected_local_model_ids=("local", "repo"),
            service_ownership="operator", provider_activation="operator_reconnect_required",
        )
        command = (str(profile.runtime_executable), *profile.serve_arguments)

        class UnhealthyRoutedTransport(FakeTransport):
            def health(self, base_url: str) -> dict[str, object]:
                payload = super().health(base_url)
                if ":1337" in base_url:
                    payload["status"] = "degraded"
                return payload

        with self.assertRaisesRegex(ValueError, "routed health"):
            collect_static_result(
                profile=profile, validator=FakeValidator(),
                process_backend=FakeProcessBackend(command),
                transport=UnhealthyRoutedTransport(), resource_probe=FakeResourceProbe(),
            )

    def test_gate_b_rejects_process_drift_during_inventory(self) -> None:
        profile = RuntimeProfile(
            profile_id="profile", revision="3", runtime_executable=Path("/optiq"),
            runtime_version="0.3.3", coordinator_model_id="gemma",
            package_versions={"mlx-optiq": "0.3.3"}, model_repository="repo",
            model_revision="abc", model_snapshot=Path("/model"),
            artifact_hashes={"model": "hash"}, serve_arguments=("serve", "--model", "/model"),
            direct_base_url="http://127.0.0.1:8080/v1",
            routed_base_url="http://127.0.0.1:1337/v1",
            direct_model_identities=("repo",), osaurus_provider_id="Optiq",
            routed_model_id="optiq/repo", rejected_local_model_ids=("local", "repo"),
            service_ownership="operator", provider_activation="operator_reconnect_required",
        )
        backend = FakeProcessBackend((str(profile.runtime_executable), *profile.serve_arguments))

        class DriftingTransport(FakeTransport):
            def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
                result = super().list_models(base_url)
                if ":1337" in base_url:
                    backend.extra = ProcessSnapshot(5252, 5000, 5252, "other", ("optiq", "lab"))
                return result

        with self.assertRaisesRegex(ValueError, "changed during inventory"):
            collect_static_result(
                profile=profile, validator=FakeValidator(), process_backend=backend,
                transport=DriftingTransport(), resource_probe=FakeResourceProbe(),
            )

    def test_gate_b_rejects_direct_health_drift_after_inventory(self) -> None:
        profile = RuntimeProfile(
            profile_id="profile", revision="3", runtime_executable=Path("/optiq"),
            runtime_version="0.3.3", coordinator_model_id="gemma",
            package_versions={"mlx-optiq": "0.3.3"}, model_repository="repo",
            model_revision="abc", model_snapshot=Path("/model"),
            artifact_hashes={"model": "hash"}, serve_arguments=("serve", "--model", "/model"),
            direct_base_url="http://127.0.0.1:8080/v1",
            routed_base_url="http://127.0.0.1:1337/v1",
            direct_model_identities=("repo",), osaurus_provider_id="Optiq",
            routed_model_id="optiq/repo", rejected_local_model_ids=("local", "repo"),
            service_ownership="operator", provider_activation="operator_reconnect_required",
        )

        class DriftingTransport(FakeTransport):
            direct_health_calls = 0

            def health(self, base_url: str) -> dict[str, object]:
                result = super().health(base_url)
                if ":8080" in base_url:
                    self.direct_health_calls += 1
                    if self.direct_health_calls > 1:
                        return {"status": "degraded"}
                return result

        transport = DriftingTransport()
        command = (str(profile.runtime_executable), *profile.serve_arguments)
        with self.assertRaisesRegex(ValueError, "health conflicted after inventory"):
            collect_static_result(
                profile=profile, validator=FakeValidator(),
                process_backend=FakeProcessBackend(command), transport=transport,
                resource_probe=FakeResourceProbe(),
            )

        self.assertEqual(transport.direct_health_calls, 2)

    def test_parses_only_the_active_harness_plugin_version(self) -> None:
        output = """
other.plugin version=9.9.9
local.jrazz.model-runtime-evaluation-harness version=0.3.0
"""
        self.assertEqual(parse_active_plugin_version(output), "0.3.0")
        self.assertIsNone(parse_active_plugin_version("other.plugin version=0.3.0"))

    def test_collects_packaged_and_active_plugin_checksums(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            packaged = root / "plugin" / "libOsaurusEvaluationHarness.dylib"
            installed = root / "home" / ".osaurus" / "Tools" / (
                "local.jrazz.model-runtime-evaluation-harness"
            ) / "0.3.0" / "libOsaurusEvaluationHarness.dylib"
            packaged.parent.mkdir(parents=True)
            installed.parent.mkdir(parents=True)
            packaged.write_bytes(b"same")
            installed.write_bytes(b"same")

            result = collect_plugin_state(
                packaged_path=packaged, home=root / "home",
                command_runner=lambda _command: SimpleNamespace(
                    returncode=0,
                    stdout="local.jrazz.model-runtime-evaluation-harness version=0.3.0\n",
                ),
            )

        self.assertEqual(result["installed_version"], "0.3.0")
        self.assertEqual(result["packaged_sha256"], result["installed_sha256"])

    def test_loads_one_exact_validated_stage_two_manifest(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = root / "manifests"
            manifests.mkdir()
            source = Path(__file__).parent / "fixtures" / "valid-stage-2.json"
            (manifests / "stage-two.json").write_bytes(source.read_bytes())

            result = load_authorized_manifest(
                root, "stage2-20260714-001", output_root=root / "output",
            )

        self.assertEqual(result["run_id"], "stage2-20260714-001")
        self.assertEqual(result["mode"], "operator_route_probe")

    def test_rejects_a_consumed_stage_two_run_id(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = root / "manifests"
            manifests.mkdir()
            source = Path(__file__).parent / "fixtures" / "valid-stage-2.json"
            manifest = json.loads(source.read_text())
            manifest["expires_at"] = "2026-07-14T23:59:59-04:00"
            (manifests / "stage-two.json").write_text(json.dumps(manifest))
            output_root = root / "output"
            consumed = output_root / "stage2-20260714-001"
            consumed.mkdir(parents=True)
            (consumed / "state.json").write_text("{}")

            with self.assertRaises(RuntimeError) as raised:
                load_authorized_manifest(
                    root, "stage2-20260714-001", output_root=output_root,
                )

        self.assertEqual(getattr(raised.exception, "code", None), "run_id_consumed")


if __name__ == "__main__":
    unittest.main()
