"""CLI wiring tests for the `browse` subcommand.

Follows the existing test_managed_run_cli.py convention: main(argv) with
redirect_stdout, parsing the emitted JSON line. No mocks; bundles are built
through the real fixture builders in a TemporaryDirectory.
"""

from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.managed_run_cli import main
from tests.results_browser_fixtures import (
    make_corrupt,
    make_sealed_pass,
    make_unsealed_running,
)


def _main_json(argv: list[str]) -> tuple[int, dict[str, object]]:
    output = StringIO()
    with redirect_stdout(output):
        code = main(argv)
    return code, json.loads(output.getvalue())


class BrowseCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_browse_happy_path_reports_ok_and_run_count(self) -> None:
        make_sealed_pass(self.root)
        make_unsealed_running(self.root)
        results_root = self.root / "results"
        output_root = self.root / "browser-out"

        code, payload = _main_json(
            [
                "browse",
                "--results-root",
                str(results_root),
                "--output",
                str(output_root),
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runs"], 2)
        self.assertEqual(payload["results_root"], str(results_root))
        self.assertEqual(payload["output"], str(output_root))
        self.assertTrue(Path(payload["index"]).is_file())
        self.assertEqual(Path(payload["index"]), output_root / "index.html")

    def test_missing_results_root_still_reports_ok_with_zero_runs(self) -> None:
        results_root = self.root / "does-not-exist"
        output_root = self.root / "browser-out"

        code, payload = _main_json(
            [
                "browse",
                "--results-root",
                str(results_root),
                "--output",
                str(output_root),
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runs"], 0)
        index_path = output_root / "index.html"
        self.assertTrue(index_path.is_file())
        self.assertIn("does not exist", index_path.read_text(encoding="utf-8").lower())

    def test_output_written_only_beneath_output_root(self) -> None:
        make_sealed_pass(self.root)
        results_root = self.root / "results"
        output_root = self.root / "nested" / "browser-out"

        before = {p for p in self.root.rglob("*") if p.is_file()}
        code, payload = _main_json(
            [
                "browse",
                "--results-root",
                str(results_root),
                "--output",
                str(output_root),
            ]
        )
        after = {p for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(code, 0)
        new_files = after - before
        self.assertTrue(new_files)
        for path in new_files:
            self.assertTrue(str(path).startswith(str(output_root)))

    def test_corrupt_bundle_does_not_crash_the_command(self) -> None:
        make_corrupt(self.root)
        results_root = self.root / "results"
        output_root = self.root / "browser-out"

        code, payload = _main_json(
            [
                "browse",
                "--results-root",
                str(results_root),
                "--output",
                str(output_root),
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runs"], 1)

    def test_default_results_root_and_output_are_wired(self) -> None:
        output = StringIO()
        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(["browse", "--help"])
        self.assertEqual(context.exception.code, 0)
        self.assertIn("--results-root", output.getvalue())
        self.assertIn("--output", output.getvalue())


if __name__ == "__main__":
    unittest.main()
