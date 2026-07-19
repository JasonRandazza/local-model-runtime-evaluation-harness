from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.benchmark_suite import BenchmarkSuite


class BenchmarkSuiteTest(unittest.TestCase):
    def test_route_overhead_suite_has_six_workloads_and_sixty_measurements(self) -> None:
        suite = BenchmarkSuite.load(Path(__file__).parents[1] / "suites" / "route-overhead-v1.json")
        schedule = suite.schedule(repetitions=5)
        measured = [request for request in schedule if request.measured]
        warmups = [request for request in schedule if not request.measured]
        self.assertEqual(len(suite.workloads), 6)
        self.assertEqual(len(measured), 60)
        self.assertEqual(len(warmups), 12)

    def test_route_order_is_counterbalanced_and_categories_invert_start(self) -> None:
        suite = BenchmarkSuite.load(Path(__file__).parents[1] / "suites" / "route-overhead-v1.json")
        schedule = suite.schedule(repetitions=5)
        starts = []
        for workload in suite.workloads:
            measured = [
                item for item in schedule if item.workload_id == workload.workload_id and item.measured
            ]
            starts.append(measured[0].route)
            self.assertEqual(sum(item.route == "direct" for item in measured), 5)
            self.assertEqual(sum(item.route == "routed" for item in measured), 5)
        self.assertEqual(starts, ["direct", "routed", "direct", "routed", "direct", "routed"])


if __name__ == "__main__":
    unittest.main()
