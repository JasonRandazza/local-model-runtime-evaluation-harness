"""Importing the package must not read configuration.

A module-scope configuration read makes every CLI crash before argument
parsing wherever configuration is absent -- which is exactly what happens to
an installed copy, since `config/` lives outside the importable package. These
tests fail loudly if an eager read is reintroduced.

The import checks run in a subprocess against a copy of the package placed
where no `config/` tree exists. That is the real installed layout, so no
monkeypatching is needed -- and, importantly, a poisoned module cache cannot
leak into the rest of the suite.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PACKAGE_NAME = "local_model_runtime_evaluation"
PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / PACKAGE_NAME

# Module-scope calls that do no I/O and are safe at import time.
_ALLOWED_MODULE_SCOPE_CALLS = frozenset(
    {"frozenset", "compile", "Path", "getLogger", "namedtuple", "TypeVar", "dict"}
)

_CLI_MODULES = (
    "managed_run_cli",
    "preference_cli",
    "rag_cli",
    "overhead_cli",
    "discovery_cli",
    "approach3_cli",
)


def _run_in_isolated_copy(body: str) -> subprocess.CompletedProcess[str]:
    """Run `body` against a package copy that has no sibling config/ tree."""
    with TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        site.mkdir()
        shutil.copytree(
            PACKAGE_DIR,
            site / PACKAGE_NAME,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        assert not (Path(tmp) / "config").exists()
        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(body)],
            cwd=tmp,
            env={"PYTHONPATH": str(site), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )


class ImportPurityTests(unittest.TestCase):
    def test_no_module_scope_configuration_reads(self) -> None:
        offenders = []
        for path in sorted(PACKAGE_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.Assign) or not isinstance(
                    node.value, ast.Call
                ):
                    continue
                function = node.value.func
                name = getattr(function, "id", None) or getattr(function, "attr", None)
                if name in _ALLOWED_MODULE_SCOPE_CALLS:
                    continue
                offenders.append(f"{path.name}:{node.lineno}: {name}()")
        self.assertEqual(
            offenders,
            [],
            "module-scope call(s) may read configuration at import time; make "
            "them lazy functions instead",
        )

    def test_cli_modules_import_without_configuration(self) -> None:
        modules = ", ".join(repr(name) for name in _CLI_MODULES)
        result = _run_in_isolated_copy(
            f"""
            import importlib
            for name in ({modules},):
                importlib.import_module("{PACKAGE_NAME}." + name)
            print("OK")
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_managed_parser_builds_without_configuration(self) -> None:
        result = _run_in_isolated_copy(
            f"""
            from {PACKAGE_NAME}.managed_run_cli import build_parser
            build_parser()
            print("OK")
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
