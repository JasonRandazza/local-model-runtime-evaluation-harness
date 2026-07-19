from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.matrix_lifecycle import LifecycleError
from local_model_runtime_evaluation.matrix_servers import ServerError, build_server


def _cell(**overrides: object) -> Cell:
    data = dict(
        cell_id="oq4_fp16__omlx",
        quant="oq4_fp16",
        server="omlx",
        base_url="http://127.0.0.1:8100/v1",
        model_id="gemma-4-12B-it-qat-oQ4-fp16",
        artifact_path="/Users/jrazz/.cache/huggingface/hub/avneetsb/gemma-4-12B-it-qat-oQ4-fp16",
        start_command=("true",),
        stop_command=(),
        health_path="/health",
        notes="",
    )
    data.update(overrides)
    return Cell(**data)  # type: ignore[arg-type]


def _osaurus(**overrides: object) -> Cell:
    data = dict(
        cell_id="jang_4m__osaurus",
        quant="jang_4m",
        server="osaurus",
        base_url="http://127.0.0.1:1337/v1",
        model_id="gemma-4-12b-it-qat-jang_4m",
        artifact_path="/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
        start_command=("osaurus", "serve", "--port", "1337", "--yes"),
        stop_command=("osaurus", "stop"),
        health_path="/health",
        notes="",
    )
    data.update(overrides)
    return Cell(**data)  # type: ignore[arg-type]


class MatrixServerTests(unittest.TestCase):
    def test_ready_when_model_appears(self) -> None:
        transport = MagicMock()
        transport.list_models.side_effect = [
            (),
            ("gemma-4-12B-it-qat-oQ4-fp16",),
        ]
        with TemporaryDirectory() as tmp:
            handle = build_server(
                _cell(), transport, Path(tmp),
                spawner=lambda cmd, log: MagicMock(stop=MagicMock()),
                port_free=lambda port: True,
            )
            handle.start()
            handle.wait_ready("gemma-4-12B-it-qat-oQ4-fp16", timeout_seconds=2)
            handle.stop()

    def test_timeout_becomes_server_error(self) -> None:
        transport = MagicMock()
        transport.list_models.return_value = ()
        with TemporaryDirectory() as tmp:
            handle = build_server(
                _cell(), transport, Path(tmp),
                spawner=lambda cmd, log: MagicMock(stop=MagicMock()),
                port_free=lambda port: True,
            )
            handle.start()
            with self.assertRaises(ServerError):
                handle.wait_ready("missing", timeout_seconds=0.2)
            handle.stop()

    def test_auth_failure_fails_fast(self) -> None:
        from local_model_runtime_evaluation.transport import TransportError

        transport = MagicMock()
        transport.list_models.side_effect = TransportError("HTTP 401")
        with TemporaryDirectory() as tmp:
            handle = build_server(
                _cell(), transport, Path(tmp),
                spawner=lambda cmd, log: MagicMock(stop=MagicMock()),
                port_free=lambda port: True,
            )
            handle.start()
            with self.assertRaises(ServerError) as ctx:
                handle.wait_ready("gemma-4-12B-it-qat-oQ4-fp16", timeout_seconds=2)
            self.assertIn("401", str(ctx.exception))
            handle.stop()

    def test_spawn_failure_becomes_server_error(self) -> None:
        transport = MagicMock()

        def boom(cmd: tuple[str, ...], log: Path) -> MagicMock:
            raise LifecycleError("spawn failed")

        with TemporaryDirectory() as tmp:
            handle = build_server(
                _cell(), transport, Path(tmp),
                spawner=boom,
                port_free=lambda port: True,
            )
            with self.assertRaises(ServerError):
                handle.start()

    def test_osaurus_skips_spawn_when_port_busy(self) -> None:
        transport = MagicMock()
        transport.list_models.return_value = ("gemma-4-12b-it-qat-jang_4m",)
        spawner = MagicMock()
        stop_runner = MagicMock()
        with TemporaryDirectory() as tmp:
            handle = build_server(
                _osaurus(), transport, Path(tmp),
                spawner=spawner,
                port_free=lambda port: False,
                stop_runner=stop_runner,
            )
            handle.start()
            spawner.assert_not_called()
            handle.wait_ready("gemma-4-12b-it-qat-jang_4m", timeout_seconds=1)
            handle.stop()
            stop_runner.assert_not_called()

    def test_process_stop_when_no_stop_command(self) -> None:
        transport = MagicMock()
        transport.list_models.return_value = ("gemma-4-12B-it-qat-oQ4-fp16",)
        process = MagicMock()
        with TemporaryDirectory() as tmp:
            handle = build_server(
                _cell(), transport, Path(tmp),
                spawner=lambda cmd, log: process,
                port_free=lambda port: True,
            )
            handle.start()
            handle.stop()
            process.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
