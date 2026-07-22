from __future__ import annotations

import unittest

from local_model_runtime_evaluation.harness_lifecycle import (
    HarnessLifecycleError,
    PORT_BY_KIND,
    ServerPin,
)


class HarnessLifecyclePinTest(unittest.TestCase):
    def test_port_by_kind_matches_spec(self) -> None:
        self.assertEqual(PORT_BY_KIND["optiq"], 8080)
        self.assertEqual(PORT_BY_KIND["omlx"], 8100)
        self.assertEqual(PORT_BY_KIND["osaurus"], 1337)

    def test_server_pin_rejects_port_mismatch(self) -> None:
        with self.assertRaises(HarnessLifecycleError) as ctx:
            ServerPin(kind="optiq", port=9999, start_command=("optiq", "serve"))
        self.assertEqual(ctx.exception.code, "port_mismatch")


if __name__ == "__main__":
    unittest.main()
