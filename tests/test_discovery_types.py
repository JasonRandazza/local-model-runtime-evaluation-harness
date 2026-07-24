from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.discovery_types import (
    DiscoveryError,
    allocate_proposal_id,
    load_proposal,
    proposal_content_hash,
    verify_proposal_hash,
    write_execution,
    write_proposal,
)


class DiscoveryTypesTests(unittest.TestCase):
    def test_content_hash_ignores_existing_hash_field(self) -> None:
        body = {
            "schema_version": "1.0.0",
            "proposal_id": "discovery-20260724-001",
            "content_hash": "should-be-ignored",
            "confirm_policy": "explicit_execute",
        }
        digest = proposal_content_hash(body)
        self.assertEqual(digest, proposal_content_hash({**body, "content_hash": "other"}))
        self.assertEqual(len(digest), 64)

    def test_write_load_and_verify_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal = {
                "schema_version": "1.0.0",
                "proposal_id": "discovery-20260724-001",
                "created_at": "2026-07-24T00:00:00+00:00",
                "confirm_policy": "explicit_execute",
                "servers": {},
                "families": {},
                "executable_families": [],
            }
            path = write_proposal(root, proposal)
            self.assertEqual(path, root / "discovery-20260724-001" / "proposal.json")
            loaded = load_proposal(root, "discovery-20260724-001")
            self.assertIn("content_hash", loaded)
            verify_proposal_hash(loaded)
            loaded["executable_families"] = ["tampered"]
            with self.assertRaises(DiscoveryError):
                verify_proposal_hash(loaded)

    def test_allocate_proposal_id_increments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 7, 24, tzinfo=timezone.utc)
            first = allocate_proposal_id(root, now=now)
            self.assertEqual(first, "discovery-20260724-001")
            (root / first).mkdir()
            second = allocate_proposal_id(root, now=now)
            self.assertEqual(second, "discovery-20260724-002")

    def test_write_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposal_dir = Path(tmp) / "discovery-20260724-001"
            proposal_dir.mkdir()
            path = write_execution(proposal_dir, {"ok": False, "steps": []})
            self.assertEqual(path, proposal_dir / "execution.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["ok"], False)


if __name__ == "__main__":
    unittest.main()
