from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_model_runtime_evaluation.credentials import Credential, FakeCredentialProvider
from local_model_runtime_evaluation.model_profiles import ModelProfileRegistry
from local_model_runtime_evaluation.operator_check import collect_operator_check


class FakeTransport:
    def list_models(self, base_url, credential):
        model_id = "omlx/VibeThinker-3B-MLX-oQ4" if ":1337" in base_url else "VibeThinker-3B-MLX-oQ4"
        return (model_id, "other")

    def health(self, base_url):
        return {"status": "healthy", "loaded": [], "current_model": None, "resident_models": [], "http_inflight": 0}


class FakeProbe:
    def free_memory_percent(self):
        return 55


class OperatorCheckTest(unittest.TestCase):
    def test_reports_non_secret_readiness_without_inference(self) -> None:
        profile = ModelProfileRegistry(Path(__file__).parents[1] / "config" / "model-profiles").get(
        "vibethinker-3b-mlx-oq4", "3"
        )
        secret = "operator-check-test-key"
        result = collect_operator_check(
            profile, FakeCredentialProvider(Credential(secret)), FakeTransport(), FakeProbe()
        )
        encoded = json.dumps(result)
        self.assertEqual(result["overall"], "READY_FOR_GATE_B_REVIEW")
        self.assertEqual(result["credential_status"], "PRESENT")
        self.assertEqual(result["coordinator_model_id"], "gemma-4-12b-it-qat-jang_4m")
        self.assertEqual(result["inference_requests_attempted"], 0)
        self.assertNotIn(secret, encoded)


if __name__ == "__main__":
    unittest.main()
