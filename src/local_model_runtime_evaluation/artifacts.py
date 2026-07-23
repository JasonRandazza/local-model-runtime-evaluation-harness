from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from .models import BenchmarkManifest


STAGE_ZERO_REQUIRED_FILES = {
    "manifest.json",
    "preflight.json",
    "inventory.json",
    "lifecycle.jsonl",
    "summary.json",
}
STAGE_ONE_REQUIRED_FILES = {
    "manifest.json", "preflight.json", "hardware.json", "endpoint-inventory.json",
    "benchmark-suite.json", "raw-runs.jsonl", "memory-samples.jsonl", "lifecycle.jsonl",
    "direct-summary.json", "routed-summary.json", "route-comparison.json", "summary.json",
    "draft-report.md",
}
STAGE_TWO_REQUIRED_FILES = {
    "manifest.json", "preflight.json", "runtime-identity.json", "artifact-identity.json",
    "process-ownership.json", "service-events.jsonl", "endpoint-inventory.json",
    "memory-samples.jsonl", "lifecycle.jsonl", "summary.json", "redacted-log.md",
}
STAGE_TWO_REVISION_THREE_REQUIRED_FILES = {
    "manifest.json", "preflight.json", "runtime-identity.json", "artifact-identity.json",
    "operator-service-identity.json", "service-events.jsonl", "request-evidence.jsonl",
    "endpoint-inventory.json", "memory-samples.jsonl", "lifecycle.jsonl", "summary.json",
}
STAGE_TWO_INFERENCE_REQUIRED_FILES = {
    "manifest.json", "preflight.json", "runtime-identity.json",
    "artifact-identity.json", "operator-service-identity.json",
    "service-events.jsonl", "request-evidence.jsonl", "post-attempts.jsonl",
    "endpoint-inventory.json", "memory-samples.jsonl", "lifecycle.jsonl",
    "inference-suite.json", "raw-runs.jsonl", "smoke-summary.json",
    "direct-observations.json", "routed-observations.json", "summary.json",
}
STAGE_TWO_BENCHMARK_REQUIRED_FILES = {
    "manifest.json", "preflight.json", "runtime-identity.json",
    "artifact-identity.json", "operator-service-identity.json",
    "service-events.jsonl", "request-evidence.jsonl", "post-attempts.jsonl",
    "endpoint-inventory.json", "memory-samples.jsonl", "lifecycle.jsonl",
    "benchmark-suite.json", "raw-runs.jsonl", "benchmark-summary.json",
    "direct-observations.json", "routed-observations.json", "summary.json",
}


class ArtifactError(RuntimeError):
    pass


@dataclass(frozen=True)
class BundleValidation:
    valid: bool
    files: tuple[str, ...]


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


class ArtifactBundle:
    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def create(cls, manifest: BenchmarkManifest, output_root: Path) -> "ArtifactBundle":
        path = output_root / manifest.run_id
        path.mkdir(parents=True, exist_ok=True)
        bundle = cls(path)
        if not (path / "manifest.json").exists():
            bundle.write_json("manifest.json", dict(manifest.raw))
        return bundle

    def write_json(self, name: str, payload: Mapping[str, object]) -> None:
        if Path(name).name != name or not name.endswith(".json"):
            raise ArtifactError("artifact name is not allowed")
        target = self.path / name
        if (self.path / "checksums.txt").exists() and target.exists():
            raise ArtifactError("finalized artifacts are immutable")
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(_json_bytes(payload))
        temporary.replace(target)

    def append_event(self, payload: Mapping[str, object]) -> None:
        self.append_jsonl("lifecycle.jsonl", payload)

    def append_jsonl(self, name: str, payload: Mapping[str, object]) -> None:
        if Path(name).name != name or not name.endswith(".jsonl"):
            raise ArtifactError("artifact name is not allowed")
        if (self.path / "checksums.txt").exists():
            raise ArtifactError("finalized artifacts are immutable")
        with (self.path / name).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def write_text(self, name: str, text: str) -> None:
        if Path(name).name != name or not name.endswith(".md"):
            raise ArtifactError("artifact name is not allowed")
        if (self.path / "checksums.txt").exists():
            raise ArtifactError("finalized artifacts are immutable")
        target = self.path / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(target)

    def _required_files(self) -> set[str]:
        try:
            manifest = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ArtifactError("manifest artifact is unavailable") from error
        if manifest.get("stage") == 2:
            if (
                manifest.get("mode") == "operator_route_benchmark"
                and manifest.get("schema_version") == "3.4.0"
                and manifest.get("runtime_profile_revision") in {"2", "3"}
            ):
                return STAGE_TWO_BENCHMARK_REQUIRED_FILES
            if (
                manifest.get("mode") == "harness_route_benchmark"
                and manifest.get("schema_version") == "3.6.0"
                and manifest.get("runtime_profile_revision") == "5"
            ):
                return STAGE_TWO_BENCHMARK_REQUIRED_FILES
            if (
                manifest.get("mode") == "operator_inference_probe"
                and (
                    (
                        manifest.get("schema_version") == "3.3.0"
                        and manifest.get("runtime_profile_revision") in {"2", "3"}
                    )
                    or (
                        manifest.get("schema_version") == "3.2.0"
                        and manifest.get("runtime_profile_revision") == "3"
                    )
                )
            ):
                return STAGE_TWO_INFERENCE_REQUIRED_FILES
            if (
                manifest.get("mode") == "harness_inference_probe"
                and manifest.get("schema_version") == "3.5.0"
                and manifest.get("runtime_profile_revision") == "4"
            ):
                return STAGE_TWO_INFERENCE_REQUIRED_FILES
            if (
                manifest.get("schema_version") == "3.1.0"
                and manifest.get("runtime_profile_revision") == "3"
            ):
                return STAGE_TWO_REVISION_THREE_REQUIRED_FILES
            return STAGE_TWO_REQUIRED_FILES
        return STAGE_ONE_REQUIRED_FILES if manifest.get("stage") == 1 else STAGE_ZERO_REQUIRED_FILES

    def _write_checksums(self) -> None:
        lines = []
        for path in sorted(self.path.iterdir(), key=lambda item: item.name):
            if not path.is_file() or path.name in {
                "checksums.txt", "checksums.txt.tmp", "state.json",
            }:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.name}")
        target = self.path / "checksums.txt"
        temporary = self.path / "checksums.txt.tmp"
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(target)

    def finalize(self, summary: Mapping[str, object]) -> None:
        self.write_json("summary.json", summary)
        missing = self._required_files() - {
            path.name for path in self.path.iterdir() if path.is_file()
        }
        if missing:
            raise ArtifactError(f"artifact bundle is incomplete: {sorted(missing)}")
        self._write_checksums()

    def finalize_partial(self, summary: Mapping[str, object]) -> None:
        self.write_json("summary.json", summary)
        present = {path.name for path in self.path.iterdir() if path.is_file()}
        required_partial = {"manifest.json", "lifecycle.jsonl", "summary.json"}
        if not required_partial.issubset(present):
            raise ArtifactError("partial artifact bundle lacks its durable run record")
        self._write_checksums()

    def reseal_after_state_transition(
        self,
        *,
        expected_lifecycle_lines: tuple[str, ...],
        prior_lifecycle_lines: tuple[str, ...] | None = None,
    ) -> None:
        """Rewrite checksums.txt after a lifecycle-only artifact change.

        ``expected_lifecycle_lines`` must equal the actual on-disk
        ``lifecycle.jsonl`` content, exactly as before. That alone is not
        sufficient: both values can be derived from the same (possibly
        tampered) current file, so a legal-looking chain prefix — e.g. a
        truncated trailing row — would trivially satisfy it. To anchor
        against tampering that predates this call and cannot be detected by
        re-reading the current file, the caller's expected history is also
        required to reconcile with the digest already sealed in
        ``checksums.txt`` for ``lifecycle.jsonl``:

        - If no new transition was written during this call
          (``prior_lifecycle_lines`` is ``None``), the current file must be
          byte-identical to what was already sealed: hashing
          ``expected_lifecycle_lines`` must reproduce the sealed digest.
          Recovery/reseal paths that perform no new transition use this
          branch, so a truncated, appended, or otherwise altered
          ``lifecycle.jsonl`` cannot be re-checksummed as authentic evidence.
        - If a new transition was written during this call, the caller
          supplies the in-memory snapshot of ``lifecycle.jsonl`` captured
          immediately before that transition was written
          (``prior_lifecycle_lines``). That snapshot, not the current file,
          must reproduce the sealed digest, proving no tampering occurred
          before this transition began.
        """
        if not (self.path / "checksums.txt").is_file():
            raise ArtifactError("artifact bundle must be finalized before resealing")
        anchor_lines = (
            expected_lifecycle_lines if prior_lifecycle_lines is None else prior_lifecycle_lines
        )
        sealed_digest = self._sealed_digest("lifecycle.jsonl")
        if sealed_digest != self._lifecycle_digest(anchor_lines):
            raise ArtifactError(
                "lifecycle history does not match the checksum already sealed "
                "for lifecycle.jsonl"
            )
        actual_lines = tuple(
            (self.path / "lifecycle.jsonl").read_text(encoding="utf-8").splitlines()
        )
        if actual_lines != tuple(expected_lifecycle_lines):
            raise ArtifactError(
                "lifecycle history does not match the expected reconciliation"
            )
        self._validate_checksums(allowed_changes={"lifecycle.jsonl"})
        self._write_checksums()

    def _sealed_digest(self, name: str) -> str:
        checksum_path = self.path / "checksums.txt"
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            digest, entry_name = line.split("  ", 1)
            if entry_name == name:
                return digest
        raise ArtifactError(f"checksums.txt has no sealed entry for {name}")

    @staticmethod
    def _lifecycle_digest(lines: tuple[str, ...]) -> str:
        content = ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
        return hashlib.sha256(content).hexdigest()

    def validate(self) -> BundleValidation:
        validation = self.validate_partial()
        if not self._required_files().issubset(set(validation.files)):
            raise ArtifactError("required artifacts are absent from checksums")
        return validation

    def validate_partial(self) -> BundleValidation:
        return self._validate_checksums()

    def _validate_checksums(
        self, *, allowed_changes: set[str] | None = None,
    ) -> BundleValidation:
        checksum_path = self.path / "checksums.txt"
        if not checksum_path.exists():
            raise ArtifactError("checksums.txt is missing")
        allowed = allowed_changes or set()
        checked = []
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            target = self.path / name
            if name in allowed:
                if not target.is_file():
                    raise ArtifactError(f"required reseal input is missing: {name}")
            elif not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ArtifactError(f"checksum mismatch: {name}")
            checked.append(name)
        return BundleValidation(valid=True, files=tuple(sorted(checked)))
