from __future__ import annotations

import unittest

from local_model_runtime_evaluation.gate_b_check import build_gate_b_report


class GateBCheckTest(unittest.TestCase):
    def test_batches_non_live_gate_b_evidence_without_inference(self) -> None:
        operator = {
            "overall": "READY_FOR_GATE_B_REVIEW",
            "profile_id": "vibethinker-3b-mlx-oq4",
            "profile_revision": "3",
            "coordinator_model_id": "gemma-4-12b-it-qat-jang_4m",
            "inference_requests_attempted": 0,
            "model_load_attempts": 0,
            "service_lifecycle_actions": 0,
        }
        result = build_gate_b_report(
            run_id="stage1-20260714-001",
            manifest_profile_revision="3",
            manifest_suite_revision="2",
            installed_version="0.2.0",
            packaged_sha256="abc",
            installed_sha256="abc",
            operator_result=operator,
        )
        self.assertEqual(result["overall"], "READY_FOR_LIVE_AUTHORIZATION")
        self.assertEqual(result["coordinator_model_id"], "gemma-4-12b-it-qat-jang_4m")
        self.assertEqual(result["inference_requests_attempted"], 0)

    def test_stops_on_plugin_or_profile_drift(self) -> None:
        operator = {
            "overall": "READY_FOR_GATE_B_REVIEW",
            "profile_revision": "3",
            "coordinator_model_id": "gemma-4-12b-it-qat-jang_4m",
            "inference_requests_attempted": 0,
        }
        result = build_gate_b_report(
            run_id="stage1-20260714-001",
            manifest_profile_revision="1",
            manifest_suite_revision="2",
            installed_version="0.2.0",
            packaged_sha256="abc",
            installed_sha256="different",
            operator_result=operator,
        )
        self.assertEqual(result["overall"], "STOPPED")
        self.assertTrue(result["manager_review_required"])


if __name__ == "__main__":
    unittest.main()
