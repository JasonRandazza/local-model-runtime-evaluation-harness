from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.overhead_report import (
    pair_deltas,
    render_overhead_report,
    write_report,
)


class PairDeltasTests(unittest.TestCase):
    def test_pair_deltas_primary_total(self) -> None:
        d = pair_deltas(
            {"median_total_seconds": 2.0, "median_ttft_seconds": 0.5},
            {"median_total_seconds": 2.5, "median_ttft_seconds": 0.8},
        )
        self.assertAlmostEqual(d["delta_median_total_seconds"], 0.5)
        self.assertAlmostEqual(d["delta_median_ttft_seconds"], 0.3)
        self.assertAlmostEqual(d["direct_median_total_seconds"], 2.0)
        self.assertAlmostEqual(d["routed_median_total_seconds"], 2.5)

    def test_pair_deltas_none_when_missing(self) -> None:
        d = pair_deltas(
            {"median_total_seconds": 2.0},
            {"median_total_seconds": None, "median_ttft_seconds": 0.8},
        )
        self.assertIsNone(d["delta_median_total_seconds"])


class RenderOverheadReportTests(unittest.TestCase):
    def test_render_includes_delta_columns(self) -> None:
        raw = {
            "mode": "screen",
            "suite_id": "gemma-matrix-v1",
            "suite_revision": "1",
            "pairs": [
                {
                    "pair_id": "oq4_fp16",
                    "direct": {"status": "PASS", "summary": {"median_total_seconds": 2.0, "median_ttft_seconds": 0.5}},
                    "routed": {"status": "PASS", "summary": {"median_total_seconds": 2.5, "median_ttft_seconds": 0.8}},
                    "deltas": pair_deltas(
                        {"median_total_seconds": 2.0, "median_ttft_seconds": 0.5},
                        {"median_total_seconds": 2.5, "median_ttft_seconds": 0.8},
                    ),
                },
            ],
        }
        report = render_overhead_report(raw)
        self.assertIn("Δ total", report)
        self.assertIn("Δ TTFT", report)
        self.assertIn("oq4_fp16", report)
        self.assertIn("later expansion", report.lower())

    def test_write_report_reads_raw_json(self) -> None:
        raw = {
            "mode": "screen",
            "suite_id": "gemma-matrix-v1",
            "suite_revision": "1",
            "pairs": [],
        }
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
            path = write_report(run_dir)
            self.assertEqual(path, run_dir / "report.md")
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
