from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.lifecycle import LifecycleStore
from local_model_runtime_evaluation.models import RunStatus


class StageOneLifecycleTest(unittest.TestCase):
    def test_stage_one_evidence_sequence_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = LifecycleStore(Path(temp))
            run_id = "stage1-20260713-001"
            store.create(run_id)
            for status in (
                RunStatus.PREFLIGHT, RunStatus.RESOURCE_GATE, RunStatus.ENDPOINT_IDENTITY,
                RunStatus.READY, RunStatus.WARMUP, RunStatus.MEASURED,
                RunStatus.ARTIFACT_VALIDATION, RunStatus.AWAITING_REVIEW, RunStatus.CLEANED,
            ):
                store.transition(run_id, status, status.value)
            self.assertEqual(store.history(run_id)[-3:], ["artifact_validation", "awaiting_review", "cleaned"])


if __name__ == "__main__":
    unittest.main()
