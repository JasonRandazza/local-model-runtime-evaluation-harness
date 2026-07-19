from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.identity import IdentityError, prove_route_identity
from local_model_runtime_evaluation.model_profiles import ModelProfileRegistry


class IdentityProofTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[1] / "config" / "model-profiles"
        self.profile = ModelProfileRegistry(root).get("vibethinker-3b-mlx-oq4", "3")

    def test_proves_both_routes_expose_approved_model(self) -> None:
        proof = prove_route_identity(
            self.profile,
            ("VibeThinker-3B-MLX-oQ4",),
            ("omlx/VibeThinker-3B-MLX-oQ4",),
        )
        self.assertTrue(proof.same_omlx_model)

    def test_rejects_missing_or_ambiguous_model(self) -> None:
        with self.assertRaises(IdentityError):
            prove_route_identity(self.profile, ("other",), ("VibeThinker-3B-MLX-oQ4",))


if __name__ == "__main__":
    unittest.main()
