from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from local_model_runtime_evaluation.discovery_cli import (
    _cmd_execute,
    _cmd_propose,
    _cmd_show,
    main as _main,
)
from local_model_runtime_evaluation.discovery_execute import DiscoverySuiteHooks
from local_model_runtime_evaluation.discovery_types import DiscoveryError, load_proposal
from local_model_runtime_evaluation.matrix_config import load_family
from tests.artifact_profile_fixtures import synthetic_artifact_roots

ROOTS = synthetic_artifact_roots()


def main(argv: list[str]) -> int:
    return _main(argv, artifact_roots=ROOTS)


class FakeTransport:
    def __init__(self) -> None:
        family = load_family("gemma-4-12b-qat").resolve(ROOTS)
        self.urls = {
            "osaurus": "http://127.0.0.1:1337/v1",
            "omlx": "http://127.0.0.1:8100/v1",
            "optiq": "http://127.0.0.1:8080/v1",
        }
        self.models = {
            self.urls["osaurus"]: tuple(family.quants["jang_4m"].model_ids),
            self.urls["omlx"]: tuple(family.quants["oq4_fp16"].model_ids),
            self.urls["optiq"]: tuple(family.quants["optiq_4bit"].model_ids),
        }

    def health(self, base_url: str) -> dict[str, object]:
        return {"status": "ok"}

    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
        return self.models[base_url]


class DiscoveryCliTests(unittest.TestCase):
    def test_dry_config_ok_no_network(self) -> None:
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = main(["dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertIn("gemma-4-12b-qat", payload["families"])

    def test_propose_show_execute_with_fakes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cells = (
                "jang_4m__osaurus",
                "oq4_fp16__omlx",
                "optiq_4bit__optiq",
            )
            summary = _cmd_propose(
                results_root=root,
                transport=FakeTransport(),
                path_exists=lambda _p: True,
                preference_recipes={"gemma-4-12b-qat": cells},
                rag_recipes={"gemma-4-12b-qat": cells},
                credential_for=lambda _server: None,
                artifact_roots=ROOTS,
            )
            self.assertTrue(summary["ok"])
            self.assertIn("gemma-4-12b-qat", summary["executable_families"])
            proposal_id = summary["proposal_id"]
            shown = _cmd_show(results_root=root, proposal_id=proposal_id)
            self.assertEqual(shown["proposal_id"], proposal_id)

            hooks = DiscoverySuiteHooks(
                run_preference=lambda family_id, cell_ids, judge_cell_id: root / "pref",
                run_rag_oracle=lambda family_id, cell_ids: root / "oracle",
                run_rag_keyword=lambda family_id, cell_ids: root / "keyword",
            )
            execution = _cmd_execute(
                results_root=root,
                proposal_id=proposal_id,
                family_id="gemma-4-12b-qat",
                hooks=hooks,
                preference_recipes={"gemma-4-12b-qat": cells},
            )
            self.assertTrue(execution["ok"])
            with self.assertRaises(DiscoveryError):
                _cmd_execute(
                    results_root=root,
                    proposal_id=proposal_id,
                    family_id="ornith-35b",
                    hooks=hooks,
                    preference_recipes={"gemma-4-12b-qat": cells},
                )
            loaded = load_proposal(root, proposal_id)
            self.assertEqual(loaded["schema_version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
