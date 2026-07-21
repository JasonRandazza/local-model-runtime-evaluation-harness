from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.rag_config import (
    DEFAULT_RAG_CELLS,
    RagCorpus,
    RagDefaults,
    RagError,
    RagSuite,
    default_rag_cells,
    load_rag_defaults,
    load_rag_family_cell_recipes,
    resolve_rag_selection,
)

ROOT = Path(__file__).resolve().parents[1]


class RagConfigTests(unittest.TestCase):
    def test_corpus_loads_six_chunks(self) -> None:
        corpus = RagCorpus.load(ROOT / "corpora/rag-oracle-v1")
        self.assertEqual(corpus.corpus_id, "rag-oracle-v1")
        self.assertEqual(len(corpus.chunks), 6)
        self.assertIn("OSAURUS_PORT=1337", corpus.get("syn-ports").text)

    def test_suite_loads_six_questions(self) -> None:
        suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
        self.assertEqual(suite.suite_id, "gemma-rag-oracle-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(suite.corpus_id, "rag-oracle-v1")
        self.assertEqual(len(suite.questions), 6)
        cells = default_rag_cells()
        self.assertEqual(len(cells), 4)
        self.assertIn("optiq_4bit__omlx", cells)
        self.assertEqual(len(DEFAULT_RAG_CELLS), 4)

    def test_defaults_load_gemma_family(self) -> None:
        defaults = load_rag_defaults()
        self.assertEqual(defaults.family_id, "gemma-4-12b-qat")
        self.assertEqual(len(defaults.cells), 4)
        self.assertIn("optiq_4bit__omlx", defaults.cells)

    def test_resolve_family_override_ornith(self) -> None:
        selection = resolve_rag_selection(family_id="ornith-35b", cells=None)
        self.assertEqual(selection.family_id, "ornith-35b")
        self.assertEqual(len(selection.cells), 4)
        self.assertTrue(all(c.startswith("ornith_") for c in selection.cells))

    def test_resolve_family_override_qwen(self) -> None:
        selection = resolve_rag_selection(family_id="qwen36-35b-a3b", cells=None)
        self.assertEqual(selection.family_id, "qwen36-35b-a3b")
        self.assertEqual(
            selection.cells,
            (
                "qwen_mxfp4__osaurus",
                "qwen_oq4__omlx",
                "qwen_optiq_4bit__omlx",
                "qwen_optiq_4bit__optiq",
            ),
        )

    def test_resolve_missing_family_fails(self) -> None:
        empty = RagDefaults(family_id="", cells=())
        with self.assertRaises(RagError):
            resolve_rag_selection(family_id=None, cells=None, defaults=empty)

    def test_gemma_defaults_match_recipe(self) -> None:
        defaults = load_rag_defaults()
        recipes = load_rag_family_cell_recipes()
        self.assertEqual(defaults.cells, recipes["gemma-4-12b-qat"])

    def test_suite_rejects_wrong_question_count(self) -> None:
        bad = {
            "schema_version": "1.0.0",
            "suite_id": "gemma-rag-oracle-v1",
            "revision": "1",
            "temperature": 0,
            "streaming": True,
            "corpus_id": "rag-oracle-v1",
            "questions": [
                {
                    "prompt_id": f"question-{index}",
                    "question": "test question",
                    "gold_chunk_ids": ["syn-ports"],
                    "required_facts": ["OSAURUS_PORT=1337"],
                    "max_tokens": 256,
                }
                for index in range(5)
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(RagError):
                RagSuite.load(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
