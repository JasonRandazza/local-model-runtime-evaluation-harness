from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.rag_config import CorpusChunk, RagCorpus, RagError
from local_model_runtime_evaluation.rag_retrieve import retrieve_top_k, tokenize

ROOT = Path(__file__).resolve().parents[1]


class RagRetrieveTests(unittest.TestCase):
    def test_tokenize_lowercases_and_splits(self) -> None:
        self.assertEqual(tokenize("OSAURUS_PORT=1337!"), ("osaurus", "port", "1337"))

    def test_retrieve_ports_query_ranks_syn_ports_first(self) -> None:
        corpus = RagCorpus.load(ROOT / "corpora/rag-oracle-v1")
        ids = retrieve_top_k(
            "What TCP ports do Osaurus oMLX OptiQ use OSAURUS_PORT OMLX_PORT OPTIQ_PORT",
            corpus,
            k=2,
        )
        self.assertEqual(ids[0], "syn-ports")
        self.assertEqual(len(ids), 2)

    def test_retrieve_tie_break_by_chunk_id(self) -> None:
        corpus = RagCorpus(
            "test",
            (
                CorpusChunk("z-last", "Z", "alpha beta shared"),
                CorpusChunk("a-first", "A", "alpha beta shared"),
            ),
        )
        ids = retrieve_top_k("alpha beta shared", corpus, k=2)
        self.assertEqual(ids, ("a-first", "z-last"))

    def test_retrieve_rejects_non_positive_k(self) -> None:
        corpus = RagCorpus(
            "test",
            (CorpusChunk("only", "Only", "text"),),
        )
        with self.assertRaises(RagError):
            retrieve_top_k("x", corpus, k=0)


if __name__ == "__main__":
    unittest.main()
