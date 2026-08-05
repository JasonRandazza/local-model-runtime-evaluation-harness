from __future__ import annotations

import unittest

from local_model_runtime_evaluation.discovery_match import (
    build_proposal,
    match_family,
    probe_servers,
    require_agreeing_recipes,
)
from local_model_runtime_evaluation.discovery_types import DiscoveryError
from local_model_runtime_evaluation.matrix_config import REPOSITORY_ROOT, load_family
from tests.artifact_profile_fixtures import synthetic_artifact_roots

ROOTS = synthetic_artifact_roots()


class FakeTransport:
    def __init__(
        self,
        *,
        health_ok: set[str] | None = None,
        models: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.health_ok = health_ok or set()
        self.models = models or {}

    def health(self, base_url: str) -> dict[str, object]:
        if base_url not in self.health_ok:
            raise RuntimeError("down")
        return {"status": "ok"}

    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
        return self.models.get(base_url, ())


class DiscoveryMatchTests(unittest.TestCase):
    def test_recipe_disagreement_raises(self) -> None:
        with self.assertRaises(DiscoveryError):
            require_agreeing_recipes(
                preference_recipes={"gemma-4-12b-qat": ("a", "b", "c")},
                rag_recipes={"gemma-4-12b-qat": ("a", "b", "d")},
            )

    def test_partial_triple_not_ready(self) -> None:
        cells_root = REPOSITORY_ROOT / "config" / "matrix" / "cells"
        family_id = "gemma-4-12b-qat"
        cell_ids = (
            "jang_4m__osaurus",
            "oq4_fp16__omlx",
            "optiq_4bit__optiq",
        )
        family = load_family(family_id).resolve(ROOTS)
        # Only osaurus reachable; pretend all artifacts exist
        osaurus = f"http://127.0.0.1:1337/v1"
        transport = FakeTransport(
            health_ok={osaurus},
            models={osaurus: tuple(family.quants["jang_4m"].model_ids)},
        )
        probe = probe_servers(transport)
        result = match_family(
            family_id=family_id,
            cell_ids=cell_ids,
            cells_root=cells_root,
            transport=transport,
            artifact_roots=ROOTS,
            server_probe=probe,
            path_exists=lambda _p: True,
        )
        self.assertFalse(result["ready"])
        self.assertFalse(result["cells"]["oq4_fp16__omlx"]["identity_ok"])
        self.assertFalse(result["cells"]["optiq_4bit__optiq"]["identity_ok"])

    def test_full_triple_ready_when_artifacts_and_ids_match(self) -> None:
        cells_root = REPOSITORY_ROOT / "config" / "matrix" / "cells"
        family_id = "gemma-4-12b-qat"
        cell_ids = (
            "jang_4m__osaurus",
            "oq4_fp16__omlx",
            "optiq_4bit__optiq",
        )
        family = load_family(family_id).resolve(ROOTS)
        urls = {
            "osaurus": "http://127.0.0.1:1337/v1",
            "omlx": "http://127.0.0.1:8100/v1",
            "optiq": "http://127.0.0.1:8080/v1",
        }
        models = {
            urls["osaurus"]: tuple(family.quants["jang_4m"].model_ids),
            urls["omlx"]: tuple(family.quants["oq4_fp16"].model_ids),
            urls["optiq"]: tuple(family.quants["optiq_4bit"].model_ids),
        }
        transport = FakeTransport(health_ok=set(urls.values()), models=models)
        probe = probe_servers(transport)
        result = match_family(
            family_id=family_id,
            cell_ids=cell_ids,
            cells_root=cells_root,
            transport=transport,
            artifact_roots=ROOTS,
            server_probe=probe,
            path_exists=lambda _p: True,
        )
        self.assertTrue(result["ready"])

        preference = {family_id: cell_ids}
        proposal = build_proposal(
            proposal_id="discovery-20260724-001",
            created_at="2026-07-24T00:00:00+00:00",
            preference_recipes=preference,
            rag_recipes=preference,
            cells_root=cells_root,
            transport=transport,
            artifact_roots=ROOTS,
            path_exists=lambda _p: True,
        )
        self.assertEqual(proposal["executable_families"], [family_id])
        self.assertEqual(proposal["confirm_policy"], "explicit_execute")


    def test_health_failure_reason_does_not_leak_exception_message(self) -> None:
        class LeakyTransport:
            def health(self, base_url: str) -> dict[str, object]:
                raise RuntimeError("secret-token-xyz")

            def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
                return ()

        probe = probe_servers(LeakyTransport())
        for server in probe.values():
            self.assertFalse(server["reachable"])
            self.assertEqual(server["reason"], "health_failed")
            self.assertNotIn("secret-token-xyz", str(server["reason"]))


if __name__ == "__main__":
    unittest.main()
