from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ModelProfileError(ValueError):
    code = "model_profile_invalid"


@dataclass(frozen=True)
class EndpointProfile:
    base_url: str
    model_id: str

    @property
    def port(self) -> int:
        return int(urlparse(self.base_url).port or 0)


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    revision: str
    runtime_owner: str
    coordinator_model_id: str
    comparison_classes: tuple[str, ...]
    direct: EndpointProfile
    routed: EndpointProfile
    tokenizer: dict[str, str]
    suite_id: str
    credential_ref: str
    limits: dict[str, object]


class ModelProfileRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, profile_id: str, revision: str) -> ModelProfile:
        matches: list[ModelProfile] = []
        for path in self.root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                profile = _parse(data)
            except (OSError, json.JSONDecodeError, ModelProfileError):
                continue
            if profile.profile_id == profile_id:
                matches.append(profile)
        if len(matches) != 1:
            raise ModelProfileError("exactly one approved model profile is required")
        profile = matches[0]
        if profile.revision != revision:
            raise ModelProfileError("model profile revision mismatch")
        return profile


def _endpoint(value: object, expected_port: int) -> EndpointProfile:
    if not isinstance(value, dict) or set(value) != {"base_url", "model_id"}:
        raise ModelProfileError("endpoint profile is invalid")
    base_url, model_id = value["base_url"], value["model_id"]
    if not isinstance(base_url, str) or not isinstance(model_id, str) or not model_id:
        raise ModelProfileError("endpoint fields are invalid")
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != expected_port or parsed.path != "/v1":
        raise ModelProfileError("endpoint is outside the approved loopback route")
    return EndpointProfile(base_url, model_id)


def _parse(data: object) -> ModelProfile:
    required = {
        "schema_version", "profile_id", "revision", "approved", "runtime_owner",
        "coordinator_model_id",
        "comparison_classes", "direct", "routed", "tokenizer", "suite_id",
        "credential_ref", "limits",
    }
    if not isinstance(data, dict) or set(data) != required:
        raise ModelProfileError("model profile fields are invalid")
    if data["schema_version"] != "1.0.0" or data["approved"] is not True:
        raise ModelProfileError("model profile is not approved")
    if data["runtime_owner"] != "omlx" or data["comparison_classes"] != ["route-overhead"]:
        raise ModelProfileError("model profile runtime or comparison class is forbidden")
    if data["coordinator_model_id"] != "gemma-4-12b-it-qat-jang_4m":
        raise ModelProfileError("coordinator model is not approved")
    tokenizer = data["tokenizer"]
    limits = data["limits"]
    if not isinstance(tokenizer, dict) or set(tokenizer) != {"kind", "identity"}:
        raise ModelProfileError("tokenizer profile is invalid")
    if not isinstance(limits, dict) or set(limits) != {"request_timeout_seconds", "memory_stop_level"}:
        raise ModelProfileError("profile limits are invalid")
    return ModelProfile(
        profile_id=str(data["profile_id"]), revision=str(data["revision"]),
        runtime_owner="omlx", coordinator_model_id=str(data["coordinator_model_id"]),
        comparison_classes=("route-overhead",),
        direct=_endpoint(data["direct"], 8100), routed=_endpoint(data["routed"], 1337),
        tokenizer={str(k): str(v) for k, v in tokenizer.items()},
        suite_id=str(data["suite_id"]), credential_ref=str(data["credential_ref"]),
        limits=dict(limits),
    )
