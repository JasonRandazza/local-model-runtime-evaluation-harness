from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from local_model_runtime_evaluation.credentials import Credential
from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.process_inspection import ProcessIdentity
from local_model_runtime_evaluation.omlx_catalog import OMLX_CATALOG_TOKEN
from local_model_runtime_evaluation.runtime_adapters.base import (
    RuntimeAdapterError,
    RuntimeContext,
)
from local_model_runtime_evaluation.runtime_adapters.omlx import OmlxAdapter
from local_model_runtime_evaluation.runtime_adapters.optiq import OptiqAdapter
from local_model_runtime_evaluation.runtime_adapters.osaurus import (
    OsaurusAdapter,
)


def _identity(
    *,
    pid: int = 321,
    argv: tuple[str, ...] = ("server",),
    port: int = 8100,
) -> ProcessIdentity:
    return ProcessIdentity(
        pid=pid,
        ppid=100,
        executable="/usr/local/bin/server",
        argv=argv,
        started_at="Thu Jul 30 18:00:00 2026",
        listener_host="127.0.0.1",
        listener_port=port,
    )


class FakeInspector:
    def __init__(self, identity: ProcessIdentity | None) -> None:
        self.identity = identity

    def inspect_listener(
        self,
        host: str,
        port: int,
    ) -> ProcessIdentity | None:
        return self.identity


class FakeTransport:
    def __init__(self, models: tuple[str, ...]) -> None:
        self.models = models

    def list_models(
        self,
        base_url: str,
        credential: object | None,
    ) -> tuple[str, ...]:
        return self.models


def _context(
    transport: FakeTransport,
    *,
    credential: Credential | None = None,
) -> RuntimeContext:
    return RuntimeContext.for_test(
        log_dir=Path("/tmp/logs"),
        credential=credential,
        transport=transport,
    )


def _osaurus() -> Cell:
    artifact = "/Users/test/models/gemma-jang"
    return Cell(
        cell_id="jang_4m__osaurus",
        quant="jang_4m",
        server="osaurus",
        base_url="http://127.0.0.1:1337/v1",
        model_id="gemma-jang",
        artifact_path=artifact,
        start_command=("osaurus", "serve", "--port", "1337", "--yes"),
        stop_command=("osaurus", "stop"),
        health_path="/health",
        notes="",
    )


def _omlx() -> Cell:
    artifact = "/Users/test/models/gemma-oq4"
    return Cell(
        cell_id="oq4__omlx",
        quant="oq4",
        server="omlx",
        base_url="http://127.0.0.1:8100/v1",
        model_id="gemma-oq4",
        artifact_path=artifact,
        start_command=(
            "omlx",
            "serve",
            "--model-dir",
            "/tmp/catalog",
            "--host",
            "127.0.0.1",
            "--port",
            "8100",
        ),
        stop_command=(),
        health_path="/health",
        notes="",
    )


def _optiq() -> Cell:
    artifact = "/Users/test/models/gemma-optiq"
    return Cell(
        cell_id="optiq__optiq",
        quant="optiq",
        server="optiq",
        base_url="http://127.0.0.1:8080/v1",
        model_id=f"{artifact}:no-think",
        artifact_path=artifact,
        start_command=(
            "optiq",
            "serve",
            "--model",
            artifact,
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--no-anthropic",
            "--no-responses",
            "--no-auth",
        ),
        stop_command=(),
        health_path="/health",
        notes="",
    )


class RuntimeAdapterTests(unittest.TestCase):
    def test_each_adapter_accepts_only_fixed_server_and_port(self) -> None:
        cases = (
            (OsaurusAdapter, _osaurus(), 1337),
            (OmlxAdapter, _omlx(), 8100),
            (OptiqAdapter, _optiq(), 8080),
        )
        for adapter_type, cell, port in cases:
            with self.subTest(adapter=adapter_type.__name__):
                adapter = adapter_type(
                    inspector=FakeInspector(None),
                    spawner=MagicMock(),
                )
                requirement = adapter.requirement_from_cell(cell)
                self.assertEqual(requirement.runtime, cell.server)
                self.assertEqual(requirement.port, port)
                self.assertEqual(requirement.model_id, cell.model_id)

    def test_adapter_rejects_wrong_server(self) -> None:
        adapter = OmlxAdapter(
            inspector=FakeInspector(None),
            spawner=MagicMock(),
        )
        with self.assertRaises(RuntimeAdapterError):
            adapter.requirement_from_cell(_osaurus())

    def test_optiq_command_is_exactly_pinned_by_cell(self) -> None:
        cell = _optiq()
        adapter = OptiqAdapter(
            inspector=FakeInspector(None),
            spawner=MagicMock(),
        )
        requirement = adapter.requirement_from_cell(cell)
        self.assertEqual(
            requirement.start_command,
            cell.start_command,
        )
        self.assertEqual(
            requirement.start_command[:4],
            ("optiq", "serve", "--model", cell.artifact_path),
        )
        self.assertIn("127.0.0.1", requirement.start_command)

    def test_start_command_with_user_selected_executable_is_rejected(self) -> None:
        adapter = OptiqAdapter(
            inspector=FakeInspector(None),
            spawner=MagicMock(),
        )
        cell = _optiq()
        unsafe = Cell(
            cell_id=cell.cell_id,
            quant=cell.quant,
            server=cell.server,
            base_url=cell.base_url,
            model_id=cell.model_id,
            artifact_path=cell.artifact_path,
            start_command=(
                "/tmp/custom-optiq",
                *cell.start_command[1:],
            ),
            stop_command=cell.stop_command,
            health_path=cell.health_path,
            notes=cell.notes,
        )
        with self.assertRaises(RuntimeAdapterError):
            adapter.requirement_from_cell(unsafe)

    def test_inventory_requires_exact_model_membership(self) -> None:
        cell = _omlx()
        identity = _identity(
            argv=cell.start_command,
            port=8100,
        )
        adapter = OmlxAdapter(
            inspector=FakeInspector(identity),
            spawner=MagicMock(),
        )
        requirement = adapter.requirement_from_cell(cell)
        compatible = adapter.inspect(
            requirement,
            _context(FakeTransport((cell.model_id,))),
        )
        missing = adapter.inspect(
            requirement,
            _context(FakeTransport((f"{cell.model_id}-other",))),
        )
        self.assertTrue(compatible.compatible)
        self.assertFalse(missing.compatible)
        self.assertEqual(missing.reason, "required_model_missing")

    def test_absent_listener_does_not_query_inventory(self) -> None:
        transport = MagicMock()
        adapter = OsaurusAdapter(
            inspector=FakeInspector(None),
            spawner=MagicMock(),
        )
        observation = adapter.inspect(
            adapter.requirement_from_cell(_osaurus()),
            _context(transport),
        )
        self.assertIsNone(observation.identity)
        self.assertEqual(observation.reason, "listener_absent")
        transport.list_models.assert_not_called()

    def test_owned_osaurus_release_uses_fixed_stop_command(self) -> None:
        process = MagicMock()
        process.pid = 222
        stop_runner = MagicMock()
        adapter = OsaurusAdapter(
            inspector=FakeInspector(None),
            spawner=MagicMock(return_value=process),
            stop_runner=stop_runner,
        )
        requirement = adapter.requirement_from_cell(_osaurus())
        lease = adapter.start(
            requirement,
            _context(FakeTransport(())),
        )

        adapter.release(lease, _context(FakeTransport(())))

        stop_runner.assert_called_once_with(("osaurus", "stop"))
        process.stop.assert_not_called()

    def test_omlx_in_memory_api_key_is_redacted_from_evidence_command(self) -> None:
        cell = _omlx()
        adapter = OmlxAdapter(
            inspector=FakeInspector(None),
            spawner=MagicMock(),
        )
        requirement = adapter.requirement_from_cell(cell)
        context = _context(
            FakeTransport(()),
            credential=Credential("local-loopback-key"),
        )
        command = adapter.start_command(requirement, context)
        self.assertEqual(command[-2:], ("--api-key", "local-loopback-key"))
        redacted = adapter.evidence_command(command)
        self.assertEqual(redacted[-2:], ("--api-key", "<redacted>"))
        self.assertNotIn("local-loopback-key", redacted)

    def test_omlx_start_and_release_own_temporary_catalog_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "weights"
            artifact.mkdir()
            cell = _omlx()
            cell = Cell(
                cell_id=cell.cell_id,
                quant=cell.quant,
                server=cell.server,
                base_url=cell.base_url,
                model_id=cell.model_id,
                artifact_path=str(artifact),
                start_command=(
                    "omlx",
                    "serve",
                    "--model-dir",
                    OMLX_CATALOG_TOKEN,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8100",
                ),
                stop_command=(),
                health_path=cell.health_path,
                notes=cell.notes,
            )
            process = MagicMock()
            process.pid = 222
            seen: list[tuple[str, ...]] = []

            def spawn(command: tuple[str, ...], log_path: Path) -> MagicMock:
                del log_path
                seen.append(command)
                return process

            adapter = OmlxAdapter(
                inspector=FakeInspector(None),
                spawner=spawn,
            )
            context = RuntimeContext.for_test(
                log_dir=root / "logs",
                credential=Credential("local-loopback-key"),
                transport=FakeTransport(()),
                catalog_root=root / "run" / "runtime" / "omlx-catalog",
            )
            lease = adapter.start(
                adapter.requirement_from_cell(cell),
                context,
            )
            self.assertNotIn(OMLX_CATALOG_TOKEN, seen[0])
            self.assertIn(str(context.catalog_root), seen[0])
            self.assertTrue(
                (context.catalog_root / cell.model_id).is_symlink()
            )
            adapter.release(lease, context)
            process.stop.assert_called_once()
            self.assertFalse(context.catalog_root.exists())
            self.assertTrue(artifact.is_dir())


if __name__ == "__main__":
    unittest.main()
