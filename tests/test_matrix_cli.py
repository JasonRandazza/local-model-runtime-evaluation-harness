from __future__ import annotations

import unittest

from local_model_runtime_evaluation.matrix_runner import main


class MatrixCliTest(unittest.TestCase):
    def test_dry_config_prints_ok(self) -> None:
        code = main(["--dry-config", "--campaign", "config/matrix/gemma-4-12b-qat-campaign.json"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
