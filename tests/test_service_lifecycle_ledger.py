from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.service_lifecycle_ledger import ServiceLifecycleLedger


class ServiceLifecycleLedgerTest(unittest.TestCase):
    def test_starts_at_zero_and_adds_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ledger = ServiceLifecycleLedger(Path(temp) / "service-lifecycle-actions.json")
            self.assertEqual(ledger.read(), 0)
            self.assertEqual(ledger.add(1), 1)
            self.assertEqual(ledger.add(1), 2)
            self.assertEqual(ledger.read(), 2)

    def test_persists_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "service-lifecycle-actions.json"
            ServiceLifecycleLedger(path).add(1)
            self.assertEqual(ServiceLifecycleLedger(path).read(), 1)
            self.assertEqual(ServiceLifecycleLedger(path).add(1), 2)


if __name__ == "__main__":
    unittest.main()
