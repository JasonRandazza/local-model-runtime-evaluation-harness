"""Temporary per-run oMLX model-directory catalogs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


OMLX_CATALOG_TOKEN = "{LMRE_OMLX_CATALOG}"
SAFE_CATALOG_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class OmlxCatalogError(RuntimeError):
    code = "omlx_catalog_failed"


@dataclass(frozen=True)
class CatalogEntry:
    model_id: str
    artifact_path: Path

    @property
    def link_name(self) -> str:
        if not SAFE_CATALOG_NAME.fullmatch(self.model_id):
            raise OmlxCatalogError(
                "oMLX model id is not a safe catalog name"
            )
        return self.model_id


@dataclass(frozen=True)
class TemporaryOmlxCatalog:
    path: Path
    entries: tuple[tuple[str, Path], ...]

    @classmethod
    def create(
        cls,
        root: Path,
        entries: tuple[CatalogEntry, ...],
    ) -> TemporaryOmlxCatalog:
        if not entries:
            raise OmlxCatalogError("oMLX catalog entries are empty")
        resolved: list[tuple[str, Path]] = []
        names: set[str] = set()
        for entry in entries:
            name = entry.link_name
            if name in names:
                raise OmlxCatalogError("oMLX catalog model ids are duplicated")
            names.add(name)
            target = entry.artifact_path.resolve()
            if not target.is_dir():
                raise OmlxCatalogError(
                    f"oMLX catalog artifact is not a directory: {entry.model_id}"
                )
            resolved.append((name, target))
        try:
            root.mkdir(parents=True, exist_ok=False)
        except FileExistsError as error:
            raise OmlxCatalogError(
                "oMLX catalog root already exists"
            ) from error
        created: list[Path] = []
        try:
            for name, target in resolved:
                link = root / name
                link.symlink_to(target, target_is_directory=True)
                created.append(link)
        except OSError as error:
            for link in reversed(created):
                link.unlink(missing_ok=True)
            root.rmdir()
            raise OmlxCatalogError(
                "oMLX catalog link creation failed"
            ) from error
        return cls(root, tuple(resolved))

    def command(self, command: tuple[str, ...]) -> tuple[str, ...]:
        if command.count(OMLX_CATALOG_TOKEN) != 1:
            raise OmlxCatalogError(
                "oMLX command must contain exactly one catalog token"
            )
        return tuple(
            str(self.path) if part == OMLX_CATALOG_TOKEN else part
            for part in command
        )

    def cleanup(self) -> None:
        if not self.path.exists():
            return
        expected = {name: target for name, target in self.entries}
        actual = {child.name: child for child in self.path.iterdir()}
        if set(actual) != set(expected):
            raise OmlxCatalogError(
                "oMLX catalog contains an unexpected entry"
            )
        for name, link in actual.items():
            if not link.is_symlink():
                raise OmlxCatalogError(
                    "oMLX catalog contains a non-symlink entry"
                )
            linked_target = link.readlink()
            if not linked_target.is_absolute():
                linked_target = (link.parent / linked_target).resolve()
            if linked_target != expected[name]:
                raise OmlxCatalogError(
                    "oMLX catalog link target changed"
                )
        for name in sorted(expected):
            actual[name].unlink()
        self.path.rmdir()
