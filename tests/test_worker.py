from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.worker import WorkerLauncher


class WorkerLauncherTest(unittest.TestCase):
    def test_worker_command_is_fixed_and_rejects_non_stage_one_id(self) -> None:
        launcher = WorkerLauncher(Path("/fixed/bin/lmre-stage0"))
        self.assertEqual(
            launcher.command("stage1-20260713-001"),
            ["/fixed/bin/lmre-stage0", "_stage1-worker", "stage1-20260713-001"],
        )
        with self.assertRaises(ValueError):
            launcher.command("stage1-20260713-001;whoami")
        self.assertTrue(launcher.matches_process_command(
            "python3 /fixed/bin/lmre-stage0 _stage1-worker stage1-20260713-001",
            "stage1-20260713-001",
        ))
        self.assertFalse(launcher.matches_process_command(
            "python3 /tmp/other _stage1-worker stage1-20260713-001",
            "stage1-20260713-001",
        ))


if __name__ == "__main__":
    unittest.main()
