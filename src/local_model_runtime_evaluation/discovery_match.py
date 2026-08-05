from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from local_model_runtime_evaluation.artifact_profile import ArtifactRoots
from local_model_runtime_evaluation.discovery_types import (
    CONFIRM_POLICY_EXPLICIT,
    DISCOVERY_SCHEMA_VERSION,
    DiscoveryError,
)
from local_model_runtime_evaluation.matrix_config import (
    SERVER_PORTS,
    Cell,
    load_family,
)

SUITE_NAMES = ("preference", "rag_oracle", "rag_keyword")


class DiscoveryTransport(Protocol):
    def health(self, base_url: str) -> dict[str, object]:
        ...

    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
        ...


def native_base_url(server: str) -> str:
    return f"http://127.0.0.1:{SERVER_PORTS[server]}/v1"


def require_agreeing_recipes(
    *,
    preference_recipes: dict[str, tuple[str, ...]],
    rag_recipes: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    shared = set(preference_recipes) & set(rag_recipes)
    agreed: dict[str, tuple[str, ...]] = {}
    for family_id in sorted(shared):
        preference_cells = preference_recipes[family_id]
        rag_cells = rag_recipes[family_id]
        if preference_cells != rag_cells:
            raise DiscoveryError(
                f"recipe disagreement for family {family_id!r}: "
                f"preference={preference_cells!r}, rag={rag_cells!r}"
            )
        agreed[family_id] = preference_cells
    return agreed


def probe_servers(
    transport: DiscoveryTransport,
    servers: tuple[str, ...] = ("osaurus", "omlx", "optiq"),
) -> dict[str, dict[str, object]]:
    probe: dict[str, dict[str, object]] = {}
    for server in servers:
        port = SERVER_PORTS[server]
        try:
            transport.health(native_base_url(server))
        except Exception as error:
            probe[server] = {
                "reachable": False,
                "port": port,
                "reason": "health_failed",
            }
        else:
            probe[server] = {
                "reachable": True,
                "port": port,
            }
    return probe


def match_family(
    *,
    family_id: str,
    cell_ids: tuple[str, ...],
    cells_root: Path,
    transport: DiscoveryTransport,
    server_probe: dict[str, dict[str, object]],
    artifact_roots: ArtifactRoots,
    credential_for: Callable[[str], object | None] | None = None,
    path_exists: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    exists = path_exists if path_exists is not None else (lambda path: Path(path).exists())
    family_template = load_family(family_id)
    family = family_template.resolve(artifact_roots)
    cells: dict[str, dict[str, object]] = {}
    all_ready = True

    for cell_id in cell_ids:
        cell = Cell.load(
            cells_root / f"{cell_id}.json",
            family=family_template,
        ).resolve(artifact_roots)
        cell.validate_for_family(family)
        artifact_ok = exists(cell.artifact_path)
        entry = server_probe[cell.server]
        reachable = bool(entry.get("reachable"))

        cell_result: dict[str, object] = {
            "artifact_ok": artifact_ok,
            "reachable": reachable,
        }

        if not reachable:
            cell_result["identity_ok"] = False
            if "reason" in entry:
                cell_result["reason"] = entry["reason"]
        else:
            try:
                credential = credential_for(cell.server) if credential_for else None
                ids = transport.list_models(native_base_url(cell.server), credential)
                quant_ids = family.quants[cell.quant].model_ids
                identity_ok = cell.model_id in ids or any(
                    model_id in ids for model_id in quant_ids
                )
            except Exception:
                identity_ok = False
                cell_result["reason"] = "inventory_failed"
            cell_result["identity_ok"] = identity_ok

        ready = artifact_ok and reachable and bool(cell_result["identity_ok"])
        cell_result["ready"] = ready
        if not ready:
            all_ready = False
        cells[cell_id] = cell_result

    return {
        "ready": all_ready,
        "cells": cells,
        "suites": list(SUITE_NAMES),
    }


def build_proposal(
    *,
    proposal_id: str,
    created_at: str,
    preference_recipes: dict[str, tuple[str, ...]],
    rag_recipes: dict[str, tuple[str, ...]],
    cells_root: Path,
    transport: DiscoveryTransport,
    artifact_roots: ArtifactRoots,
    credential_for: Callable[[str], object | None] | None = None,
    path_exists: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    agreed = require_agreeing_recipes(
        preference_recipes=preference_recipes,
        rag_recipes=rag_recipes,
    )
    servers = probe_servers(transport)
    families: dict[str, dict[str, object]] = {}
    for family_id, cell_ids in sorted(agreed.items()):
        families[family_id] = match_family(
            family_id=family_id,
            cell_ids=cell_ids,
            cells_root=cells_root,
            transport=transport,
            server_probe=servers,
            artifact_roots=artifact_roots,
            credential_for=credential_for,
            path_exists=path_exists,
        )
    executable_families = sorted(
        family_id for family_id, block in families.items() if block["ready"]
    )
    return {
        "schema_version": DISCOVERY_SCHEMA_VERSION,
        "proposal_id": proposal_id,
        "created_at": created_at,
        "confirm_policy": CONFIRM_POLICY_EXPLICIT,
        "servers": servers,
        "families": families,
        "executable_families": executable_families,
    }
