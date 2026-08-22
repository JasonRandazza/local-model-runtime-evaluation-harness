from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.cell_metrics import (
    preference_rows,
    rag_rows,
    step_json,
)
from local_model_runtime_evaluation.evidence_bundle import EvidenceBundle
from local_model_runtime_evaluation.managed_run_types import ManagedStep
from tests.results_browser_fixtures import make_sealed_pass


class CellMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        run_dir = make_sealed_pass(root)          # a sealed bundle
        bundle = EvidenceBundle.load(run_dir)
        self.run_dir = run_dir
        self.state = bundle.state
        self.plan = bundle.plan

    def _preference_step(self):
        record = next(r for r in self.state.steps if r.step is ManagedStep.PREFERENCE)
        return record.step, record.output_path

    def _seal_step(self):
        record = next(r for r in self.state.steps if r.step is ManagedStep.SEAL)
        return record.step, record.output_path

    def _pref_payload(self) -> dict:
        cells = {}
        for i, cell_id in enumerate(self.plan.cell_ids):
            wins = i + 1
            cells[cell_id] = {
                "wins": wins,
                "losses": 7 - wins,
                "ties": 0,
                "win_rate": round(wins / 7, 3),
            }
        return {"cells": cells}

    def _rag_oracle_payload(self) -> dict:
        cells = {}
        for i, cell_id in enumerate(self.plan.cell_ids):
            cells[cell_id] = {
                "mean_hit_rate": round(0.8 + 0.05 * (i + 1), 3),
            }
        return {"mode": "oracle", "cells": cells}

    def _rag_keyword_payload(self) -> dict:
        cells = {}
        for i, cell_id in enumerate(self.plan.cell_ids):
            cells[cell_id] = {
                "mean_hit_rate": round(0.8 + 0.05 * (i + 1), 3),
                "mean_recall": round(0.25 + 0.05 * (i + 1), 3),
                "mean_precision": round(0.25 + 0.02 * (i + 1), 3),
            }
        return {"mode": "keyword", "cells": cells}

    # --- step_json -------------------------------------------------------

    def test_step_json_reads_tally_from_preference_step(self) -> None:
        result = step_json(self.run_dir, self.state, ManagedStep.PREFERENCE, "tally.json")
        self.assertIsNotNone(result)
        self.assertIn("cells", result)
        self.assertEqual(len(result["cells"]), len(self.plan.cell_ids))

    def test_step_json_returns_none_for_absent_filename(self) -> None:
        step, _ = self._preference_step()
        self.assertIsNone(step_json(self.run_dir, self.state, step, "nope.json"))

    def test_step_json_returns_none_for_seal_step(self) -> None:
        seal_step, output_path = self._seal_step()
        self.assertIsNone(output_path)
        self.assertIsNone(step_json(self.run_dir, self.state, seal_step, "tally.json"))

    # --- preference_rows -------------------------------------------------

    def test_preference_rows_well_formed(self) -> None:
        cells = {}
        for i, cell_id in enumerate(self.plan.cell_ids):
            wins = i + 1
            cells[cell_id] = {
                "wins": wins,
                "losses": 7 - wins,
                "ties": 0,
                "win_rate": round(wins / 7, 3),
            }
        expected = [
            {
                "cell_id": cell_id,
                "wins": i + 1,
                "losses": 7 - (i + 1),
                "ties": 0,
                "win_rate": round((i + 1) / 7, 3),
            }
            for i, cell_id in enumerate(self.plan.cell_ids)
        ]
        self.assertEqual(preference_rows({"cells": cells}, self.plan), expected)

    def test_preference_rows_missing_cell_returns_none(self) -> None:
        payload = self._pref_payload()
        del payload["cells"][self.plan.cell_ids[-1]]
        self.assertIsNone(preference_rows(payload, self.plan))

    def test_preference_rows_extra_unknown_cell_returns_none(self) -> None:
        payload = self._pref_payload()
        payload["cells"]["not-a-real-cell"] = {
            "wins": 1,
            "losses": 6,
            "ties": 0,
            "win_rate": round(1 / 7, 3),
        }
        self.assertIsNone(preference_rows(payload, self.plan))

    def test_preference_rows_string_wins_returns_none(self) -> None:
        payload = self._pref_payload()
        cells = {cid: dict(entry) for cid, entry in payload["cells"].items()}
        cells[self.plan.cell_ids[0]]["wins"] = "3"
        self.assertIsNone(preference_rows({"cells": cells}, self.plan))

    def test_preference_rows_bool_wins_returns_none(self) -> None:
        """`isinstance(True, int)` is True; a bool must be rejected."""
        payload = self._pref_payload()
        cells = {cid: dict(entry) for cid, entry in payload["cells"].items()}
        cells[self.plan.cell_ids[0]]["wins"] = True
        self.assertIsNone(preference_rows({"cells": cells}, self.plan))

    def test_preference_rows_none_win_rate_is_accepted(self) -> None:
        payload = self._pref_payload()
        payload["cells"][self.plan.cell_ids[0]]["win_rate"] = None
        rows = preference_rows(payload, self.plan)
        self.assertIsNotNone(rows)
        self.assertIsNone(rows[0]["win_rate"])

    def test_preference_rows_none_payload_returns_none(self) -> None:
        self.assertIsNone(preference_rows(None, self.plan))

    def test_preference_rows_cells_as_list_returns_none(self) -> None:
        self.assertIsNone(preference_rows({"cells": []}, self.plan))

    # --- rag_rows --------------------------------------------------------

    def test_rag_rows_oracle_sets_only_fact_hit_rate(self) -> None:
        expected = [
            {
                "cell_id": cell_id,
                "fact_hit_rate": round(0.8 + 0.05 * (i + 1), 3),
                "retrieval_recall": None,
                "retrieval_precision": None,
            }
            for i, cell_id in enumerate(self.plan.cell_ids)
        ]
        self.assertEqual(rag_rows(self._rag_oracle_payload(), self.plan), expected)

    def test_rag_rows_keyword_sets_all_three(self) -> None:
        expected = [
            {
                "cell_id": cell_id,
                "fact_hit_rate": round(0.8 + 0.05 * (i + 1), 3),
                "retrieval_recall": round(0.25 + 0.05 * (i + 1), 3),
                "retrieval_precision": round(0.25 + 0.02 * (i + 1), 3),
            }
            for i, cell_id in enumerate(self.plan.cell_ids)
        ]
        self.assertEqual(rag_rows(self._rag_keyword_payload(), self.plan), expected)

    def test_rag_rows_keyword_missing_mean_recall_returns_none(self) -> None:
        payload = self._rag_keyword_payload()
        del payload["cells"][self.plan.cell_ids[0]]["mean_recall"]
        self.assertIsNone(rag_rows(payload, self.plan))

    def test_rag_rows_unknown_mode_returns_none(self) -> None:
        self.assertIsNone(rag_rows({"mode": "banana", "cells": {}}, self.plan))

    def test_rag_rows_missing_mean_hit_rate_returns_none(self) -> None:
        payload = self._rag_keyword_payload()
        del payload["cells"][self.plan.cell_ids[0]]["mean_hit_rate"]
        self.assertIsNone(rag_rows(payload, self.plan))


if __name__ == "__main__":
    unittest.main()
