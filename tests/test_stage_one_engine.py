from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.benchmark_suite import BenchmarkSuite
from local_model_runtime_evaluation.credentials import Credential, FakeCredentialProvider
from local_model_runtime_evaluation.manifest import load_manifest
from local_model_runtime_evaluation.model_profiles import ModelProfileRegistry
from local_model_runtime_evaluation.resources import MemoryPressure, ResourceSnapshot
from local_model_runtime_evaluation.stage_one import StageOneEngine
from local_model_runtime_evaluation.transport import TransportResult


class FakeTransport:
    def __init__(self):
        self.credentials = []

    def list_models(self, base_url, credential):
        self.credentials.append((base_url, credential))
        model_id = "omlx/VibeThinker-3B-MLX-oQ4" if ":1337" in base_url else "VibeThinker-3B-MLX-oQ4"
        return (model_id,)

    def chat(self, base_url, model_id, prompt, max_tokens, credential, cancel=None):
        self.credentials.append((base_url, credential))
        routed = ":1337" in base_url
        total = 1.1 if routed else 1.0
        content = '{"name":"status","arguments":{"run_id":"stage1-test","include_details":false}}' if "JSON object" in prompt else "ok"
        return TransportResult(content, "hash", 0.1, total, 10, "stop", 200, True, 2, 0.6, 2, 8, "EXACT_VISIBLE")


class StageOneEngineTest(unittest.TestCase):
    def test_fake_end_to_end_run_writes_reconciled_artifacts(self) -> None:
        root = Path(__file__).parents[1]
        manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-1.json",
            now=datetime(2026, 7, 13, tzinfo=timezone.utc),
        )
        profile = ModelProfileRegistry(root / "config" / "model-profiles").get(
            manifest.model_profile_id, manifest.model_profile_revision
        )
        suite = BenchmarkSuite.load(root / "suites" / "route-overhead-v1.json")
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport()
            engine = StageOneEngine(
                manifest, profile, suite, Path(temp), FakeCredentialProvider(Credential("test-key")),
                ResourceSnapshot(MemoryPressure.NORMAL, (), None), transport,
            )
            preflight = engine.preflight()
            self.assertEqual(preflight["state"], "ready")
            self.assertEqual(preflight["manifest_validation"], "PASS")
            self.assertEqual(preflight["manifest"]["model_profile_revision"], "3")
            self.assertEqual(preflight["manifest"]["suite_revision"], "2")
            self.assertEqual(preflight["credential_status"], "PRESENT")
            self.assertEqual(preflight["route_identity"], "PASS")
            self.assertEqual(preflight["service_lifecycle_actions"], 0)
            self.assertEqual(engine.run(threading.Event())["measured_sample_count"], 60)
            cleanup = engine.cleanup()
            self.assertEqual(cleanup["artifact_validation"], "PASS")
            self.assertEqual(cleanup["disposition"], "PASS")
            self.assertEqual(cleanup["measured_requests"], 60)
            self.assertEqual(cleanup["excluded_warmups"], 12)
            self.assertEqual(cleanup["direct_samples_per_workload"], 5)
            self.assertEqual(cleanup["routed_samples_per_workload"], 5)
            self.assertEqual(cleanup["response_contract_validation"], "PASS")
            self.assertEqual(cleanup["streaming_metric_status"], "COMPARABLE")
            self.assertEqual(cleanup["ttft_metric_status"], "COMPARABLE")
            self.assertEqual(cleanup["decode_metric_status"], "COMPARABLE")
            self.assertEqual(cleanup["token_accounting_status"], "EXACT_VISIBLE")
            self.assertEqual(cleanup["paired_total_seconds"]["pair_count"], 30)
            self.assertNotIn("test-key", "".join(path.read_text() for path in (Path(temp) / manifest.run_id).iterdir() if path.is_file()))
            self.assertTrue(all(credential is None for url, credential in transport.credentials if ":1337" in url))
            self.assertTrue(all(credential is not None for url, credential in transport.credentials if ":8100" in url))


if __name__ == "__main__":
    unittest.main()
