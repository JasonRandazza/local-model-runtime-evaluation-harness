from __future__ import annotations

import unittest
from unittest.mock import patch

from local_model_runtime_evaluation.inventory import collect_inventory


class InventoryTest(unittest.TestCase):
    @patch("local_model_runtime_evaluation.inventory.shutil.which")
    def test_inventory_uses_passive_path_lookup(self, which) -> None:
        which.side_effect = lambda name: f"/mock/{name}"
        result = collect_inventory()
        self.assertEqual(set(result["commands"]), {"osaurus", "optiq", "python3", "swift"})
        self.assertTrue(all(item["present"] for item in result["commands"].values()))
        self.assertEqual(which.call_count, 4)


if __name__ == "__main__":
    unittest.main()
