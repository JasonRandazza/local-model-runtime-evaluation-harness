from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.lifecycle import LifecycleStore
from local_model_runtime_evaluation.models import RunStatus


class CancellationTest(unittest.TestCase):
    def test_cancel_and_cleanup_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = LifecycleStore(Path(temp))
            run_id = "stage0-20260713-001"
            store.create(run_id)
            first = store.transition(run_id, RunStatus.CANCELLED, "operator request")
            second = store.transition(run_id, RunStatus.CANCELLED, "operator request")
            cleaned = store.transition(run_id, RunStatus.CLEANED, "cleanup")
            repeated = store.transition(run_id, RunStatus.CLEANED, "cleanup")
            self.assertEqual(first.sequence, second.sequence)
            self.assertEqual(cleaned.sequence, repeated.sequence)


if __name__ == "__main__":
    unittest.main()
