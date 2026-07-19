from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import time
import threading
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlparse

from .stage_two import (
    HostValidation, ModelDescriptor, ProcessOwnership, StageTwoError,
    direct_health_is_safe,
)
from .stage_two_profiles import RuntimeProfile


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str]):
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)


class HostValidator:
    def __init__(
        self, profile: RuntimeProfile, provider_config: Path,
        command_runner: Callable[[list[str]], object] = _run,
        hash_file: Callable[[Path], str] = _sha256,
    ) -> None:
        self.profile = profile
        self.provider_config = provider_config
        self.command_runner = command_runner
        self.hash_file = hash_file

    def _runtime(self) -> dict[str, object]:
        if not self.profile.runtime_executable.is_file():
            raise StageTwoError("runtime_identity_failed", "canonical mlx-optiq executable is unavailable")
        script = (
            "import importlib.metadata as m,json;"
            "print(json.dumps({n:m.version(n) for n in "
            "['mlx-optiq','mlx','mlx-lm','transformers']},sort_keys=True))"
        )
        package_result = self.command_runner([
            str(self.profile.runtime_executable.parent / "python"), "-c", script,
        ])
        if getattr(package_result, "returncode", 1) != 0:
            raise StageTwoError("runtime_identity_failed", "canonical package versions are unavailable")
        try:
            packages = json.loads(getattr(package_result, "stdout", ""))
        except json.JSONDecodeError as error:
            raise StageTwoError("runtime_identity_failed", "canonical package versions are invalid") from error
        if not isinstance(packages, dict) or packages.get("mlx-optiq") != self.profile.runtime_version:
            raise StageTwoError("runtime_identity_failed", "canonical mlx-optiq package version is invalid")
        return {
            "executable": str(self.profile.runtime_executable),
            "version": str(packages["mlx-optiq"]),
            "packages": packages,
        }

    def _artifact(self) -> dict[str, object]:
        if not self.profile.model_snapshot.is_dir():
            raise StageTwoError("artifact_identity_failed", "pinned OptiQ model snapshot is unavailable")
        hashes: dict[str, str] = {}
        for name in sorted(self.profile.artifact_hashes):
            path = self.profile.model_snapshot / name
            if not path.is_file():
                raise StageTwoError("artifact_identity_failed", "a pinned OptiQ artifact file is unavailable")
            hashes[name] = self.hash_file(path)
        return {
            "repository": self.profile.model_repository,
            "revision": self.profile.model_revision,
            "snapshot": str(self.profile.model_snapshot),
            "hashes": hashes,
        }

    def _provider(self) -> dict[str, object]:
        try:
            payload = json.loads(self.provider_config.read_text(encoding="utf-8"))
            providers = payload["providers"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise StageTwoError("provider_identity_failed", "Osaurus provider configuration is unavailable") from error
        if not isinstance(providers, list):
            raise StageTwoError("provider_identity_failed", "Osaurus provider configuration is invalid")
        matches = [value for value in providers if isinstance(value, dict) and value.get("name") == self.profile.osaurus_provider_id]
        if len(matches) != 1:
            raise StageTwoError("provider_identity_failed", "exactly one approved OptiQ provider is required")
        provider = matches[0]
        headers = provider.get("customHeaders", {})
        secret_header_keys = provider.get("secretHeaderKeys", [])
        if not isinstance(headers, (dict, list)):
            raise StageTwoError("provider_identity_failed", "OptiQ provider header metadata is invalid")
        if not isinstance(secret_header_keys, list):
            raise StageTwoError("provider_identity_failed", "OptiQ provider secret-header metadata is invalid")
        if (
            provider.get("host") != "127.0.0.1"
            or provider.get("port") != 8080
            or provider.get("basePath") != "/v1"
            or provider.get("providerProtocol") != "http"
            or provider.get("providerType") != "openai"
        ):
            raise StageTwoError("provider_identity_failed", "OptiQ provider endpoint is not approved")
        return {
            "provider_id": self.profile.osaurus_provider_id,
            "enabled": provider.get("enabled") is True,
            "endpoint": "127.0.0.1:8080",
            "custom_header_count": len(headers),
            "secret_header_key_count": len(secret_header_keys),
        }

    def validate(self) -> HostValidation:
        return HostValidation(self._runtime(), self._artifact(), self._provider())


@dataclass(frozen=True)
class ProcessSnapshot:
    pid: int
    parent_pid: int
    process_group_id: int
    started_at: str
    command: tuple[str, ...]


class ProcessBackend(Protocol):
    def port_is_free(self) -> bool: ...
    def listener_process_ids(self) -> tuple[int, ...]: ...
    def optiq_processes(self) -> tuple[ProcessSnapshot, ...]: ...
    def spawn(self, command: tuple[str, ...], log_path: Path) -> ProcessSnapshot: ...
    def describe(self, pid: int) -> ProcessSnapshot | None: ...
    def terminate_group(self, process_group_id: int, force: bool) -> None: ...
    def wait_exit(self, pid: int, timeout_seconds: int) -> bool: ...


class MacProcessBackend:
    def __init__(self) -> None:
        self._children: dict[int, subprocess.Popen[bytes]] = {}

    @staticmethod
    def _command_hash(command: tuple[str, ...]) -> str:
        return hashlib.sha256("\0".join(command).encode()).hexdigest()

    def port_is_free(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.25)
            return probe.connect_ex(("127.0.0.1", 8080)) != 0

    def listener_process_ids(self) -> tuple[int, ...]:
        result = subprocess.run(
            ["/usr/sbin/lsof", "-nP", "-iTCP@127.0.0.1:8080", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        if result.returncode not in {0, 1}:
            return ()
        try:
            return tuple(sorted({int(value) for value in result.stdout.split()}))
        except ValueError:
            return ()

    def _snapshots(self, pid: int | None = None) -> tuple[ProcessSnapshot, ...]:
        command = ["/bin/ps"]
        if pid is None:
            command.extend(["-axo", "pid=,ppid=,pgid=,lstart=,command="])
        else:
            command.extend(["-p", str(pid), "-o", "pid=,ppid=,pgid=,lstart=,command="])
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5)
        if result.returncode != 0:
            return ()
        snapshots: list[ProcessSnapshot] = []
        for line in result.stdout.splitlines():
            fields = line.strip().split(None, 8)
            if len(fields) != 9:
                continue
            try:
                argv = tuple(shlex.split(fields[8]))
                snapshots.append(ProcessSnapshot(
                    int(fields[0]), int(fields[1]), int(fields[2]), " ".join(fields[3:8]), argv,
                ))
            except (ValueError, IndexError):
                continue
        return tuple(snapshots)

    def optiq_processes(self) -> tuple[ProcessSnapshot, ...]:
        matches = []
        for snapshot in self._snapshots():
            for index, value in enumerate(snapshot.command[:-1]):
                if Path(value).name == "optiq" and snapshot.command[index + 1] in {"lab", "serve"}:
                    matches.append(snapshot)
                    break
        return tuple(matches)

    def spawn(self, command: tuple[str, ...], log_path: Path) -> ProcessSnapshot:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                list(command), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                start_new_session=True, close_fds=True,
            )
        self._children[process.pid] = process
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            snapshot = self.describe(process.pid)
            if snapshot is not None:
                return snapshot
            if process.poll() is not None:
                break
            time.sleep(0.05)
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        raise StageTwoError("service_start_failed", "owned OptiQ process identity could not be recorded")

    def describe(self, pid: int) -> ProcessSnapshot | None:
        snapshots = self._snapshots(pid)
        return snapshots[0] if len(snapshots) == 1 else None

    def terminate_group(self, process_group_id: int, force: bool) -> None:
        os.killpg(process_group_id, signal.SIGKILL if force else signal.SIGTERM)

    def wait_exit(self, pid: int, timeout_seconds: int) -> bool:
        child = self._children.get(pid)
        if child is not None:
            try:
                child.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                return False
            finally:
                if child.poll() is not None:
                    self._children.pop(pid, None)
            return True
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.describe(pid) is None:
                return True
            time.sleep(0.1)
        return self.describe(pid) is None


class OptiQLifecycleController:
    def __init__(
        self, approved_command: tuple[str, ...], backend: ProcessBackend,
        health_probe: Callable[[], dict[str, object]],
    ) -> None:
        self.approved_command = approved_command
        self.backend = backend
        self.health_probe = health_probe

    @staticmethod
    def _command_hash(command: tuple[str, ...]) -> str:
        return hashlib.sha256("\0".join(command).encode()).hexdigest()

    def assert_available(self) -> None:
        if not self.backend.port_is_free():
            raise StageTwoError("service_conflict", "loopback port 8080 is already occupied")
        if self.backend.optiq_processes():
            raise StageTwoError("service_conflict", "OptiQ Lab or service is already running")

    def start(self, command: tuple[str, ...], log_path: Path) -> ProcessOwnership:
        if command != self.approved_command:
            raise StageTwoError("command_forbidden", "OptiQ launch command differs from the approved profile")
        snapshot = self.backend.spawn(command, log_path)
        return ProcessOwnership(
            snapshot.pid, snapshot.parent_pid, snapshot.process_group_id,
            snapshot.started_at, self._command_hash(snapshot.command),
        )

    def is_owned(self, ownership: ProcessOwnership) -> bool:
        snapshot = self.backend.describe(ownership.pid)
        return snapshot is not None and (
            snapshot.parent_pid == ownership.parent_pid
            and snapshot.process_group_id == ownership.process_group_id
            and snapshot.started_at == ownership.started_at
            and self._command_hash(snapshot.command) == ownership.command_sha256
        )

    def wait_ready(
        self, ownership: ProcessOwnership, timeout_seconds: int, cancel: threading.Event
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if cancel.is_set():
                raise StageTwoError("cancelled", "Stage 2A was cancelled during service startup")
            if not self.is_owned(ownership):
                raise StageTwoError("ownership_mismatch", "owned OptiQ service identity changed")
            try:
                health = self.health_probe()
                if health.get("status") == "ok":
                    return health
            except Exception:
                pass
            time.sleep(0.25)
        raise StageTwoError("service_start_timeout", "owned OptiQ service did not become ready")

    def stop(self, ownership: ProcessOwnership, timeout_seconds: int) -> None:
        if not self.is_owned(ownership):
            raise StageTwoError("ownership_mismatch", "owned OptiQ service identity changed")
        self.backend.terminate_group(ownership.process_group_id, False)
        if self.backend.wait_exit(ownership.pid, timeout_seconds):
            return
        if not self.is_owned(ownership):
            raise StageTwoError("ownership_mismatch", "owned OptiQ service identity changed before escalation")
        self.backend.terminate_group(ownership.process_group_id, True)
        if not self.backend.wait_exit(ownership.pid, 5):
            raise StageTwoError("service_stop_failed", "owned OptiQ service did not stop")

    def port_is_free(self) -> bool:
        return self.backend.port_is_free()


class OperatorOptiQController:
    """Observe the operator-owned OptiQ service without controlling its lifecycle."""

    def __init__(
        self, approved_command: tuple[str, ...], backend: ProcessBackend,
        health_probe: Callable[[], dict[str, object]],
    ) -> None:
        self.approved_command = approved_command
        self.backend = backend
        self.health_probe = health_probe

    @staticmethod
    def _command_hash(command: tuple[str, ...]) -> str:
        return hashlib.sha256("\0".join(command).encode()).hexdigest()

    def _is_approved_command(self, command: tuple[str, ...]) -> bool:
        if command == self.approved_command:
            return True
        if len(command) != len(self.approved_command) + 1:
            return False
        return (
            Path(command[0]).name.startswith("python")
            and command[1:] == self.approved_command
        )

    @staticmethod
    def _is_lab(snapshot: ProcessSnapshot) -> bool:
        return any(
            Path(value).name == "optiq" and snapshot.command[index + 1:index + 2] == ("lab",)
            for index, value in enumerate(snapshot.command)
        )

    def _health_is_safe(self, health: dict[str, object]) -> bool:
        try:
            model_argument = self.approved_command[
                self.approved_command.index("--model") + 1
            ]
        except (ValueError, IndexError):
            return False
        return direct_health_is_safe(health, (model_argument,))

    def _matching_snapshot(self, identity: ProcessOwnership) -> ProcessSnapshot | None:
        snapshot = self.backend.describe(identity.pid)
        if snapshot is None:
            return None
        if (
            snapshot.parent_pid != identity.parent_pid
            or snapshot.process_group_id != identity.process_group_id
            or snapshot.started_at != identity.started_at
            or self._command_hash(snapshot.command) != identity.command_sha256
            or not self._is_approved_command(snapshot.command)
        ):
            return None
        return snapshot

    def capture(self) -> ProcessOwnership:
        processes = self.backend.optiq_processes()
        if any(self._is_lab(snapshot) for snapshot in processes):
            raise StageTwoError("operator_identity_failed", "OptiQ Lab must be closed")
        approved = tuple(snapshot for snapshot in processes if self._is_approved_command(snapshot.command))
        if len(approved) != 1 or len(processes) != 1:
            raise StageTwoError("operator_identity_failed", "exactly one canonical OptiQ serve process is required")
        snapshot = approved[0]
        if self.backend.port_is_free() or self.backend.listener_process_ids() != (snapshot.pid,):
            raise StageTwoError("operator_identity_failed", "OptiQ must be the exact 127.0.0.1:8080 listener")
        health = self.health_probe()
        if not self._health_is_safe(health):
            raise StageTwoError(
                "operator_health_failed",
                "OptiQ health must be available and contain no conflicting model diagnostics",
            )
        return ProcessOwnership(
            snapshot.pid, snapshot.parent_pid, snapshot.process_group_id,
            snapshot.started_at, self._command_hash(snapshot.command),
        )

    def matches(self, identity: ProcessOwnership) -> bool:
        snapshot = self._matching_snapshot(identity)
        processes = self.backend.optiq_processes()
        return (
            snapshot is not None
            and len(processes) == 1
            and processes[0].pid == snapshot.pid
            and not self.backend.port_is_free()
            and self.backend.listener_process_ids() == (snapshot.pid,)
        )

    def assert_stopped(self, identity: ProcessOwnership) -> None:
        if self._matching_snapshot(identity) is not None:
            raise StageTwoError("operator_shutdown_pending", "recorded OptiQ service is still running")
        if self.backend.optiq_processes():
            raise StageTwoError("operator_shutdown_pending", "an OptiQ process remains after operator shutdown")
        if not self.backend.port_is_free() or not self.backend.port_is_free():
            raise StageTwoError("operator_shutdown_pending", "127.0.0.1:8080 must be free twice after operator shutdown")


class StageTwoReadOnlyTransport:
    def __init__(self, allowed_base_urls: set[str], timeout_seconds: int) -> None:
        self.allowed_base_urls = frozenset(value.rstrip("/") for value in allowed_base_urls)
        self.timeout_seconds = timeout_seconds

    def _request(self, base_url: str, path: str) -> dict[str, object]:
        normalized = base_url.rstrip("/")
        if normalized not in self.allowed_base_urls:
            raise StageTwoError("endpoint_forbidden", "endpoint is outside the Stage 2A profile")
        if path not in {"/health", "/v1/models"}:
            raise StageTwoError("endpoint_forbidden", "Stage 2A permits health and model inventory only")
        parsed = urlparse(normalized)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
            raise StageTwoError("endpoint_forbidden", "Stage 2A allows loopback HTTP only")
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=self.timeout_seconds)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            body = response.read()
            if response.status != 200:
                raise StageTwoError("transport_failed", f"GET endpoint returned HTTP {response.status}")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise StageTwoError("transport_failed", "GET endpoint payload is invalid")
            return payload
        except StageTwoError:
            raise
        except (OSError, TimeoutError, json.JSONDecodeError) as error:
            raise StageTwoError("transport_failed", "GET endpoint request failed") from error
        finally:
            connection.close()

    def health(self, base_url: str) -> dict[str, object]:
        return self._request(base_url, "/health")

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        payload = self._request(base_url, "/v1/models")
        values = payload.get("data")
        if not isinstance(values, list):
            raise StageTwoError("transport_failed", "model inventory payload is invalid")
        descriptors: list[ModelDescriptor] = []
        for item in values:
            if not isinstance(item, dict):
                raise StageTwoError("transport_failed", "model inventory payload is invalid")
            model_id = item.get("id")
            owned_by = item.get("owned_by")
            root = item.get("root")
            if (
                not isinstance(model_id, str)
                or not model_id
                or (owned_by is not None and not isinstance(owned_by, str))
                or (root is not None and not isinstance(root, str))
            ):
                raise StageTwoError("transport_failed", "model inventory payload is invalid")
            descriptors.append(ModelDescriptor(model_id, owned_by, root))
        return tuple(descriptors)
