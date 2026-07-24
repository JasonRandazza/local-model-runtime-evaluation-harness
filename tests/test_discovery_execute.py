from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.discovery_execute import (
    DiscoverySuiteHooks,
    execute_proposal,
)
from local_model_runtime_evaluation.discovery_types import (
    DiscoveryError,
    write_proposal,
)


class DiscoveryExecuteTests(unittest.TestCase):
    def _proposal(self, root: Path, family_id: str = "gemma-4-12b-qat") -> str:
        proposal_id = "discovery-20260724-001"
        write_proposal(root, {
            "schema_version": "1.0.0",
            "proposal_id": proposal_id,
            "created_at": "2026-07-24T00:00:00+00:00",
            "confirm_policy": "explicit_execute",
            "servers": {},
            "families": {family_id: {"ready": True, "cells": {}, "suites": []}},
            "executable_families": [family_id],
        })
        return proposal_id

    def test_rejects_family_not_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = self._proposal(root)
            hooks = DiscoverySuiteHooks(
                run_preference=lambda *a, **k: Path("/nope"),
                run_rag_oracle=lambda *a, **k: Path("/nope"),
                run_rag_keyword=lambda *a, **k: Path("/nope"),
            )
            with self.assertRaises(DiscoveryError):
                execute_proposal(
                    results_root=root,
                    proposal_id=proposal_id,
                    family_id="ornith-35b",
                    hooks=hooks,
                    preference_recipes={"gemma-4-12b-qat": ("a", "b", "c")},
                )

    def test_stops_after_preference_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = self._proposal(root)
            calls: list[str] = []

            def fail_pref(family_id: str, cell_ids: tuple[str, ...], judge_cell_id: str) -> Path:
                calls.append("preference")
                raise RuntimeError("collect failed")

            def rag_ok(name: str):
                def _inner(family_id: str, cell_ids: tuple[str, ...]) -> Path:
                    calls.append(name)
                    return root / name
                return _inner

            hooks = DiscoverySuiteHooks(
                run_preference=fail_pref,
                run_rag_oracle=rag_ok("rag_oracle"),
                run_rag_keyword=rag_ok("rag_keyword"),
            )
            result = execute_proposal(
                results_root=root,
                proposal_id=proposal_id,
                family_id="gemma-4-12b-qat",
                hooks=hooks,
                preference_recipes={
                    "gemma-4-12b-qat": ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
                },
            )
            self.assertFalse(result["ok"])
            self.assertEqual(calls, ["preference"])
            self.assertEqual(result["steps"][0]["status"], "FAIL")
            execution = json.loads(
                (root / proposal_id / "execution.json").read_text(encoding="utf-8")
            )
            self.assertFalse(execution["ok"])

    def test_full_pipeline_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = self._proposal(root)
            calls: list[str] = []

            def pref(family_id: str, cell_ids: tuple[str, ...], judge_cell_id: str) -> Path:
                self.assertEqual(judge_cell_id, "jang_4m__osaurus")
                calls.append("preference")
                return root / "pref"

            def rag_ok(name: str):
                def _inner(family_id: str, cell_ids: tuple[str, ...]) -> Path:
                    calls.append(name)
                    return root / name
                return _inner

            hooks = DiscoverySuiteHooks(
                run_preference=pref,
                run_rag_oracle=rag_ok("rag_oracle"),
                run_rag_keyword=rag_ok("rag_keyword"),
            )
            result = execute_proposal(
                results_root=root,
                proposal_id=proposal_id,
                family_id="gemma-4-12b-qat",
                hooks=hooks,
                preference_recipes={
                    "gemma-4-12b-qat": ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
                },
            )
            self.assertTrue(result["ok"])
            self.assertEqual(calls, ["preference", "rag_oracle", "rag_keyword"])


if __name__ == "__main__":
    unittest.main()
