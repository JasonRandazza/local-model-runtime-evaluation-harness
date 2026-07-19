from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from local_model_runtime_evaluation.cli import main


class CliTest(unittest.TestCase):
    def test_inventory_returns_tool_contract_envelope(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["inventory"])
        envelope = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["tool"], "inventory")

    def test_unknown_command_is_rejected_by_parser(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["shell", "whoami"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
