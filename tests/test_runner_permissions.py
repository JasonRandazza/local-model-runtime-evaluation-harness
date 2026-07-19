from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.models import Operation
from local_model_runtime_evaluation.runner import RunnerError, StageZeroRunner


class RunnerPermissionsTest(unittest.TestCase):
    def test_non_inventory_operation_requires_run_id(self) -> None:
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temp:
            runner = StageZeroRunner(root, output_root_override=Path(temp))
            with self.assertRaises(RunnerError) as raised:
                runner.dispatch(Operation.PREFLIGHT)
            self.assertEqual(raised.exception.code, "run_id_required")

    def test_inventory_starts_no_process_and_makes_no_network_call(self) -> None:
        root = Path(__file__).parents[1]
        runner = StageZeroRunner(root)
        result = runner.dispatch(Operation.INVENTORY)
        self.assertEqual(result["processes_started"], 0)
        self.assertEqual(result["network_calls_attempted"], 0)


if __name__ == "__main__":
    unittest.main()
