from __future__ import annotations

import unittest

from local_model_runtime_evaluation.resources import HostResourceProbe, MemoryPressure, ResourceGateError, ResourcePolicy, ResourceSnapshot, snapshot_from_health


class ResourcePolicyTest(unittest.TestCase):
    coordinator = "gemma-4-12b-it-qat-jang_4m"

    def test_accepts_no_native_model_or_exact_idle_coordinator(self) -> None:
        policy = ResourcePolicy(self.coordinator)
        result = policy.evaluate(ResourceSnapshot(MemoryPressure.NORMAL, (), None))
        self.assertTrue(result.allowed)
        result = policy.evaluate(ResourceSnapshot(MemoryPressure.NORMAL, (self.coordinator,), None))
        self.assertTrue(result.allowed)

    def test_rejects_critical_pressure_unapproved_native_model_and_competing_run(self) -> None:
        policy = ResourcePolicy(self.coordinator)
        cases = [
            ResourceSnapshot(MemoryPressure.CRITICAL, (), None),
            ResourceSnapshot(MemoryPressure.NORMAL, ("other",), None),
            ResourceSnapshot(MemoryPressure.NORMAL, (self.coordinator, "other"), None),
            ResourceSnapshot(MemoryPressure.NORMAL, (), "stage1-other"),
        ]
        for snapshot in cases:
            with self.subTest(snapshot=snapshot), self.assertRaises(ResourceGateError):
                policy.evaluate(snapshot)

    def test_health_loaded_fields_prove_native_residency_and_memory_thresholds(self) -> None:
        snapshot = snapshot_from_health(18, {"loaded": ["native"], "current_model": "native", "resident_models": []}, None)
        self.assertEqual(snapshot.memory_pressure, MemoryPressure.WARNING)
        self.assertTrue(snapshot.osaurus_native_model_loaded)
        self.assertEqual(snapshot.osaurus_native_models, ("native",))
        self.assertEqual(snapshot_from_health(8, {"loaded": [], "current_model": None, "resident_models": []}, None).memory_pressure, MemoryPressure.CRITICAL)

    def test_health_accepts_named_resident_diagnostics(self) -> None:
        model = "gemma-4-12b-it-qat-jang_4m"
        snapshot = snapshot_from_health(
            50,
            {
                "loaded": [model],
                "current_model": model,
                "resident_models": [{"name": model, "inflight": 0, "is_current": True}],
            },
            None,
        )
        self.assertEqual(snapshot.osaurus_native_models, (model,))

    def test_parses_macos_free_memory_percentage(self) -> None:
        self.assertEqual(HostResourceProbe.parse_free_percentage("System-wide memory free percentage: 42%"), 42)


if __name__ == "__main__":
    unittest.main()
