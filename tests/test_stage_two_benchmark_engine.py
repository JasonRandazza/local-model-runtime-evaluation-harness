from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from local_model_runtime_evaluation.manifest import load_manifest
from local_model_runtime_evaluation.resources import MemoryPressure, ResourceSnapshot
from local_model_runtime_evaluation.stage_two import (
    HostValidation,
    ModelDescriptor,
    ProcessOwnership,
    StageTwoError,
)
from local_model_runtime_evaluation.stage_two_benchmark import StageTwoBenchmarkEngine
from local_model_runtime_evaluation.stage_two_factory import build_stage_two_engine
from local_model_runtime_evaluation.stage_two_benchmark_suite import (
    BenchmarkRequest,
    StageTwoBenchmarkSuite,
)
from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfileRegistry
from local_model_runtime_evaluation.transport import TransportResult


class FakeController:
    def __init__(self) -> None:
        self.identity = ProcessOwnership(4242, 4000, 4242, "started", "command")
        self.running = True

    def capture(self) -> ProcessOwnership:
        return self.identity

    def matches(self, identity: ProcessOwnership) -> bool:
        return self.running and identity == self.identity

    def assert_stopped(self, identity: ProcessOwnership) -> None:
        if self.running:
            raise StageTwoError("operator_shutdown_pending", "still running")


class FakeTransport:
    def __init__(
        self,
        *,
        fail_chat_at: int | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self.chat_calls: list[tuple[str, str]] = []
        self.fail_chat_at = fail_chat_at
        self.in_flight = 0
        self.max_in_flight = 0

    def health(self, base_url: str) -> dict[str, object]:
        route = "direct" if ":8080" in base_url else "routed"
        self.calls.append(("GET", f"{route}_health"))
        return {"status": "ok" if route == "direct" else "healthy"}

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        route = "direct" if ":8080" in base_url else "routed"
        self.calls.append(("GET", f"{route}_models"))
        if route == "direct":
            return (ModelDescriptor(
                "/Users/jrazz/.cache/huggingface/hub/"
                "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think"
            ),)
        return (ModelDescriptor(
            "optiq//Users/jrazz/.cache/huggingface/hub/"
            "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think"
        ),)

    def chat(
        self, base_url: str, model_id: str, prompt: str, max_tokens: int,
        cancel: threading.Event,
    ) -> TransportResult:
        route = "direct" if ":8080" in base_url else "routed"
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.chat_calls.append((route, model_id))
        try:
            attempt = len(self.chat_calls)
            if self.fail_chat_at == attempt:
                raise StageTwoError(
                    "transport_failed",
                    "Stage 2B benchmark transport failed",
                    reason="timeout",
                )
            if "Return exactly" in prompt:
                content = (
                    '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}'
                )
            else:
                content = (
                    "Reproducible measurements make comparisons reliable. They expose drift."
                )
            return TransportResult(
                content, "a" * 64, 0.1, 1.0, 10, "stop",
                200, True, 2, 0.5, 2, 8, "EXACT_VISIBLE",
            )
        finally:
            self.in_flight -= 1


class StageTwoBenchmarkEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-benchmark-gemma.json",
            now=datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        self.profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
            self.manifest.runtime_profile_id, self.manifest.runtime_profile_revision,
        )
        self.suite = StageTwoBenchmarkSuite.load(
            self.root / "suites" / "gemma-optiq-route-benchmark-v1.json",
        )
        self.validation = HostValidation(
            runtime_identity={"version": "0.3.3", "packages": dict(self.profile.package_versions)},
            artifact_identity={
                "revision": self.profile.model_revision,
                "hashes": dict(self.profile.artifact_hashes),
            },
            provider_identity={
                "provider_id": "Optiq", "enabled": True,
                "custom_header_count": 0, "secret_header_key_count": 0,
            },
        )

    def _engine(
        self, output: Path, transport: FakeTransport, controller: FakeController,
    ) -> StageTwoBenchmarkEngine:
        return StageTwoBenchmarkEngine(
            self.manifest, self.profile, self.suite, output,
            lambda _health: ResourceSnapshot(MemoryPressure.NORMAL, (), None),
            lambda: self.validation, controller, transport,
            lambda: self.manifest.run_id,
        )

    def _complete_and_shutdown(
        self, output: Path, transport: FakeTransport | None = None,
    ) -> tuple[StageTwoBenchmarkEngine, FakeController, FakeTransport]:
        controller = FakeController()
        actual_transport = transport or FakeTransport()
        engine = self._engine(output, actual_transport, controller)
        engine.preflight()
        engine.run(threading.Event())
        controller.running = False
        return engine, controller, actual_transport

    def test_happy_path_runs_seventy_two_posts_with_pass_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport()
            engine = self._engine(output, transport, FakeController())
            engine.preflight()
            result = engine.run(threading.Event())
            self.assertEqual(result["state"], "awaiting_review")
            self.assertEqual(result["inference_path_acceptance"], "PASS")
            self.assertEqual(result["behavioral_contract_acceptance"], "PASS")
            self.assertEqual(result["http_post_attempts"], 72)
            self.assertEqual(len(transport.chat_calls), 72)
            self.assertEqual(transport.max_in_flight, 1)
            raw = (output / self.manifest.run_id / "raw-runs.jsonl").read_text()
            self.assertEqual(len(raw.splitlines()), 72)
            self.assertNotIn("Reproducible", raw)

    def test_stops_before_seventy_third_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport()
            engine = self._engine(output, transport, FakeController())
            base = engine.suite.schedule()
            extra = base + (
                BenchmarkRequest(
                    base[-1].workload_id,
                    base[-1].route,
                    base[-1].measured,
                    73,
                    99,
                ),
            )
            class ExtendedSchedule:
                def __init__(self, suite, schedule):
                    self._suite = suite
                    self._schedule = schedule

                def schedule(self):
                    return self._schedule

                def __getattr__(self, name):
                    return getattr(self._suite, name)

            engine.suite = ExtendedSchedule(engine.suite, extra)
            engine.preflight()
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self.assertEqual(context.exception.code, "request_limit_exceeded")
            self.assertEqual(len(transport.chat_calls), 72)

    def test_first_transport_failure_stops_with_failed_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport(fail_chat_at=1)
            controller = FakeController()
            engine = self._engine(output, transport, controller)
            engine.preflight()
            with self.assertRaises(StageTwoError):
                engine.run(threading.Event())
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "failed")
            self.assertEqual(len(transport.chat_calls), 1)
            journal_path = output / self.manifest.run_id / "post-attempts.jsonl"
            phases = [
                json.loads(line)["phase"]
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("failed", phases)

    def test_cleanup_requires_manual_shutdown_before_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = FakeController()
            engine = self._engine(output, FakeTransport(), controller)
            engine.preflight()
            engine.run(threading.Event())
            with self.assertRaises(StageTwoError) as context:
                engine.cleanup()
            self.assertEqual(context.exception.code, "cleanup_failed")
            self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_cleanup_seals_complete_redacted_pass_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            engine, _, _ = self._complete_and_shutdown(output)
            result = engine.cleanup()
            run_dir = output / self.manifest.run_id
            self.assertEqual(result["disposition"], "PASS")
            self.assertEqual(result["inference_path_acceptance"], "PASS")
            self.assertEqual(result["behavioral_contract_acceptance"], "PASS")
            self.assertEqual(result["checksum_validation"], "PASS")
            self.assertIn("route_overhead_summary", result)
            self.assertIn("route_overhead_deltas", result)
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["route_overhead_summary"], result["route_overhead_summary"])
            self.assertEqual(summary["route_overhead_deltas"], result["route_overhead_deltas"])
            artifact_bytes = b"".join(
                path.read_bytes() for path in run_dir.iterdir() if path.is_file()
            )
            for forbidden in (
                b"In two sentences, explain why reproducible measurements matter.",
                b"Return exactly this JSON object with no markdown or extra text:",
                b"Reproducible measurements make comparisons reliable.",
                b"Authorization", b"Bearer", b"fake-secret",
            ):
                self.assertNotIn(forbidden, artifact_bytes)
            self.assertFalse((run_dir / "draft-report.md").exists())
            self.assertFalse((run_dir / "route-comparison.json").exists())
            self.assertNotIn(b"stable_median", artifact_bytes)

    def test_rejects_wrong_manifest_mode(self) -> None:
        altered = replace(self.manifest, mode="operator_inference_probe")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Stage 2B-2"):
                StageTwoBenchmarkEngine(
                    altered, self.profile, self.suite, Path(temp),
                    lambda _health: ResourceSnapshot(MemoryPressure.NORMAL, (), None),
                    lambda: self.validation, FakeController(), FakeTransport(),
                    lambda: altered.run_id,
                )


class StageTwoBenchmarkFactoryTest(unittest.TestCase):
    def test_factory_builds_benchmark_engine_for_valid_3_4_0_fixture(self) -> None:
        root = Path(__file__).parents[1]
        manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-benchmark-gemma.json",
            now=datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as output_temp:
            engine = build_stage_two_engine(root, manifest, Path(output_temp))
        self.assertIsInstance(engine, StageTwoBenchmarkEngine)
        self.assertEqual(engine.suite.suite_id, "gemma-optiq-route-benchmark-v1")
        self.assertEqual(engine.manifest.schema_version, "3.4.0")

    def test_factory_rejects_3_3_0_suite_id_on_3_4_0_mode(self) -> None:
        root = Path(__file__).parents[1]
        manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-benchmark-gemma.json",
            now=datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        bad_manifest = replace(manifest, suite_id="gemma-optiq-route-smoke-v1")
        with self.assertRaisesRegex(ValueError, "unsupported Stage 2 mode"):
            build_stage_two_engine(root, bad_manifest, Path(tempfile.mkdtemp()))

    def test_factory_rejects_revision_three_on_live_gemma_schemas(self) -> None:
        root = Path(__file__).parents[1]
        smoke = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json",
            now=datetime(2026, 7, 20, tzinfo=timezone.utc),
        )
        benchmark = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-benchmark-gemma.json",
            now=datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        with patch("local_model_runtime_evaluation.stage_two_factory.RuntimeProfileRegistry") as registry, patch(
            "local_model_runtime_evaluation.stage_two_factory.StageTwoSmokeSuite.load"
        ) as smoke_suite, patch(
            "local_model_runtime_evaluation.stage_two_factory.StageTwoBenchmarkSuite.load"
        ) as benchmark_suite, patch(
            "local_model_runtime_evaluation.stage_two_factory.StageTwoInferenceTransport"
        ) as transport, patch(
            "local_model_runtime_evaluation.stage_two_factory.OperatorOptiQController"
        ) as controller:
            for manifest in (
                replace(smoke, runtime_profile_revision="3"),
                replace(benchmark, runtime_profile_revision="3"),
            ):
                with self.subTest(schema_version=manifest.schema_version):
                    with self.assertRaisesRegex(ValueError, "unsupported Stage 2 mode"):
                        build_stage_two_engine(root, manifest, Path(tempfile.mkdtemp()))

        registry.assert_not_called()
        smoke_suite.assert_not_called()
        benchmark_suite.assert_not_called()
        transport.assert_not_called()
        controller.assert_not_called()


if __name__ == "__main__":
    unittest.main()
