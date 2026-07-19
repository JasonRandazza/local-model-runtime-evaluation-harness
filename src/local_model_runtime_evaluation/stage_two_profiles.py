from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class RuntimeProfileError(ValueError):
    code = "runtime_profile_invalid"


@dataclass(frozen=True)
class RuntimeProfile:
    profile_id: str
    revision: str
    runtime_executable: Path
    runtime_version: str
    coordinator_model_id: str
    package_versions: dict[str, str]
    model_repository: str
    model_revision: str
    model_snapshot: Path
    artifact_hashes: dict[str, str]
    serve_arguments: tuple[str, ...]
    direct_base_url: str
    routed_base_url: str
    direct_model_identities: tuple[str, ...]
    osaurus_provider_id: str
    routed_model_id: str
    rejected_local_model_ids: tuple[str, ...]
    service_ownership: str | None = None
    provider_activation: str | None = None


_BASE_FIELDS = {
    "schema_version", "profile_id", "revision", "approved", "runtime_executable",
    "runtime_version", "coordinator_model_id", "package_versions", "model_repository", "model_revision",
    "model_snapshot", "artifact_hashes", "serve_arguments", "direct_base_url",
    "routed_base_url", "direct_model_identities", "osaurus_provider_id",
    "routed_model_id", "rejected_local_model_ids",
}
_REVISION_THREE_FIELDS = _BASE_FIELDS | {"service_ownership", "provider_activation"}
_EXECUTABLE = Path("/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/optiq")
_SNAPSHOT = Path(
    "/Users/jrazz/.cache/huggingface/hub/"
    "models--mlx-community--VibeThinker-3B-OptiQ-4bit/snapshots/"
    "94bce93443d4f62946ae89261f62e0ecdbb1ef1e"
)
_HASH_FILES = {
    "model.safetensors", "config.json", "optiq_metadata.json", "model.safetensors.index.json"
}


def _parse(data: object) -> RuntimeProfile:
    if not isinstance(data, dict) or (
        set(data) != _BASE_FIELDS and set(data) != _REVISION_THREE_FIELDS
    ):
        raise RuntimeProfileError("runtime profile fields are invalid")
    revision = data.get("revision")
    if data["schema_version"] != "1.0.0" or revision not in {"2", "3"} or data["approved"] is not True:
        raise RuntimeProfileError("runtime profile is not approved")
    if revision == "2" and set(data) != _BASE_FIELDS:
        raise RuntimeProfileError("revision 2 profile fields are invalid")
    if revision == "3" and set(data) != _REVISION_THREE_FIELDS:
        raise RuntimeProfileError("revision 3 profile fields are invalid")
    executable = Path(str(data["runtime_executable"]))
    snapshot = Path(str(data["model_snapshot"]))
    if executable != _EXECUTABLE or snapshot != _SNAPSHOT:
        raise RuntimeProfileError("runtime or model path is not canonical")
    if data["runtime_version"] != "0.3.3":
        raise RuntimeProfileError("runtime version is not approved")
    if data["coordinator_model_id"] != "gemma-4-12b-it-qat-jang_4m":
        raise RuntimeProfileError("coordinator model is not approved")
    packages = data["package_versions"]
    if packages != {
        "mlx-optiq": "0.3.3", "mlx": "0.32.0", "mlx-lm": "0.31.3",
        "transformers": "5.12.1",
    }:
        raise RuntimeProfileError("package versions are not approved")
    hashes = data["artifact_hashes"]
    if not isinstance(hashes, dict) or set(hashes) != _HASH_FILES:
        raise RuntimeProfileError("artifact hash inventory is invalid")
    if any(not isinstance(value, str) or len(value) != 64 for value in hashes.values()):
        raise RuntimeProfileError("artifact hashes are invalid")
    arguments = data["serve_arguments"]
    if not isinstance(arguments, list) or any(not isinstance(value, str) for value in arguments):
        raise RuntimeProfileError("serve arguments are invalid")
    expected_arguments = [
        "serve", "--model", str(_SNAPSHOT), "--host", "127.0.0.1", "--port", "8080",
        "--no-anthropic", "--no-responses", "--no-auth", "--single-model",
        "--max-concurrent", "1", "--idle-timeout", "0", "--max-context", "8192",
        "--context-scale", "1.0", "--no-stream-experts", "--decode-concurrency", "1",
        "--prompt-concurrency", "1",
    ]
    if arguments != expected_arguments:
        raise RuntimeProfileError("serve arguments differ from the approved API-only command")
    if data["direct_base_url"] != "http://127.0.0.1:8080/v1" or data["routed_base_url"] != "http://127.0.0.1:1337/v1":
        raise RuntimeProfileError("runtime routes are not approved")
    identities = data["direct_model_identities"]
    if not isinstance(identities, list) or identities != [str(data["model_repository"]), str(snapshot)]:
        raise RuntimeProfileError("direct model identities are invalid")
    if data["model_repository"] != "mlx-community/VibeThinker-3B-OptiQ-4bit":
        raise RuntimeProfileError("model repository is not approved")
    if data["model_revision"] != "94bce93443d4f62946ae89261f62e0ecdbb1ef1e":
        raise RuntimeProfileError("model revision is not approved")
    routed_model_id = data["routed_model_id"]
    rejected_local_model_ids = data["rejected_local_model_ids"]
    if not isinstance(rejected_local_model_ids, list) or any(
        not isinstance(value, str) for value in rejected_local_model_ids
    ):
        raise RuntimeProfileError("Osaurus route identity is invalid")
    if revision == "2":
        expected_routed_model_id = "mlx-community/VibeThinker-3B-OptiQ-4bit"
        expected_rejected_model_ids = ["vibethinker-3b-optiq-4bit"]
        service_ownership = None
        provider_activation = None
    else:
        expected_routed_model_id = "optiq/mlx-community/VibeThinker-3B-OptiQ-4bit"
        expected_rejected_model_ids = [
            "vibethinker-3b-optiq-4bit",
            "mlx-community/VibeThinker-3B-OptiQ-4bit",
        ]
        if (
            data["service_ownership"] != "operator"
            or data["provider_activation"] != "operator_reconnect_required"
        ):
            raise RuntimeProfileError("revision 3 ownership contract is invalid")
        service_ownership = str(data["service_ownership"])
        provider_activation = str(data["provider_activation"])
    if (
        data["osaurus_provider_id"] != "Optiq"
        or routed_model_id != expected_routed_model_id
        or rejected_local_model_ids != expected_rejected_model_ids
        or routed_model_id in rejected_local_model_ids
    ):
        raise RuntimeProfileError("Osaurus route identity is invalid")
    return RuntimeProfile(
        profile_id=str(data["profile_id"]), revision=str(data["revision"]),
        runtime_executable=executable, runtime_version=str(data["runtime_version"]),
        coordinator_model_id=str(data["coordinator_model_id"]),
        package_versions={str(key): str(value) for key, value in packages.items()},
        model_repository=str(data["model_repository"]), model_revision=str(data["model_revision"]),
        model_snapshot=snapshot, artifact_hashes={str(key): str(value) for key, value in hashes.items()},
        serve_arguments=tuple(arguments), direct_base_url=str(data["direct_base_url"]),
        routed_base_url=str(data["routed_base_url"]),
        direct_model_identities=tuple(str(value) for value in identities),
        osaurus_provider_id=str(data["osaurus_provider_id"]),
        routed_model_id=str(routed_model_id),
        rejected_local_model_ids=tuple(str(value) for value in rejected_local_model_ids),
        service_ownership=service_ownership,
        provider_activation=provider_activation,
    )


class RuntimeProfileRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, profile_id: str, revision: str) -> RuntimeProfile:
        matches: list[RuntimeProfile] = []
        for path in self.root.glob("*.json"):
            try:
                profile = _parse(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, RuntimeProfileError):
                continue
            if profile.profile_id == profile_id and profile.revision == revision:
                matches.append(profile)
        if len(matches) != 1:
            raise RuntimeProfileError("exactly one approved runtime profile revision is required")
        return matches[0]
