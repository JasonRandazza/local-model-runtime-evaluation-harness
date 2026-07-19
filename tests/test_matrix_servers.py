from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.matrix_servers import ServerError, build_server


def _cell(**overrides: object) -> Cell:
    data = dict(
        cell_id="oq4_fp16__omlx",
        quant="oq4_fp16",
        server="omlx",
        base_url="http://127.0.0.1:8100/v1",
        model_id="gemma-4-12B-it-qat-oQ4-fp16",
        artifact_path="/Users/jrazz/.cache/huggingface/hub/models--avneetsb--gemma-4-12B-it-qat-oQ4-fp16",
        start_command=("true",),
        stop_command=(),
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


if __name__ == "__main__":
    unittest.main()
