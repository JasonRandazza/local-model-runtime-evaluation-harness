from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.lifecycle import LifecycleError, LifecycleStore
from local_model_runtime_evaluation.models import RunStatus


class LifecycleTest(unittest.TestCase):
    def test_legal_transitions_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = LifecycleStore(Path(temp))
            store.create("stage0-20260713-001")
            store.transition("stage0-20260713-001", RunStatus.PREFLIGHT, "validated")
            state = store.transition("stage0-20260713-001", RunStatus.READY, "ready")
            self.assertEqual(state.status, RunStatus.READY)
            self.assertEqual(state.sequence, 2)

    def test_illegal_transition_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = LifecycleStore(Path(temp))
            store.create("stage0-20260713-001")
            with self.assertRaises(LifecycleError):
                store.transition("stage0-20260713-001", RunStatus.COMPLETE, "skip")

    def test_operator_observation_transitions_without_start_or_stop_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = LifecycleStore(Path(temp))
            run_id = "stage2-20260715-999"
            store.create(run_id)
            for status in (
                RunStatus.PREFLIGHT, RunStatus.RESOURCE_GATE, RunStatus.READY,
                RunStatus.RUNNING, RunStatus.SERVICE_READY, RunStatus.ENDPOINT_IDENTITY,
                RunStatus.ARTIFACT_VALIDATION, RunStatus.AWAITING_REVIEW,
            ):
                store.transition(run_id, status, status.value)
            history = store.history(run_id)
            self.assertNotIn("service_starting", history)
            self.assertNotIn("service_stopping", history)


if __name__ == "__main__":
    unittest.main()
