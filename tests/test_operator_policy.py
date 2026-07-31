from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.operator_policy import (
    AdoptedPolicy,
    OperatorPolicy,
    PolicyError,
    PolicyRequest,
    adopt_policy,
    authorize,
    load_adopted_policy,
    load_policy,
)


def _policy_document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": "1.0.0",
        "policy_id": "local-managed-v1",
        "authorization_mode": "standing_local",
        "loopback_only": True,
        "allowed_runtimes": ["osaurus", "omlx", "optiq"],
        "allow_inference": True,
        "allow_start": True,
        "allow_exact_reclaim": True,
        "reclaim_grace_seconds": 60,
        "allow_terminate_after_interrupt": True,
        "allow_force_kill": False,
        "allow_provider_edits": False,
        "max_parallel_models": 1,
        "memory_floor_percent": 20,
        "max_run_minutes": 90,
        "max_requests_per_run": 250,
        "expires_at": None,
    }
    document.update(overrides)
    return document


def _request(**overrides: object) -> PolicyRequest:
    values: dict[str, object] = {
        "runtimes": frozenset({"osaurus", "omlx", "optiq"}),
        "endpoints": (
            "http://127.0.0.1:1337/v1",
            "http://127.0.0.1:8100/v1",
            "http://127.0.0.1:8080/v1",
        ),
        "inference": True,
        "start": True,
        "exact_reclaim": True,
        "parallel_models": 1,
        "memory_floor_percent": 20,
        "estimated_minutes": 90,
        "request_count": 250,
    }
    values.update(overrides)
    return PolicyRequest(**values)  # type: ignore[arg-type]


class OperatorPolicyTests(unittest.TestCase):
    def test_example_is_not_authority_until_adopted(self) -> None:
        with TemporaryDirectory() as tmp:
            state_root = Path(tmp) / ".lmre"
            with self.assertRaises(PolicyError) as context:
                load_adopted_policy(state_root)
            self.assertEqual(context.exception.code, "operator_policy_missing")

    def test_adopt_round_trip_preserves_hash_and_timestamp(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "policy.json"
            source.write_text(
                json.dumps(_policy_document()),
                encoding="utf-8",
            )
            adopted = adopt_policy(
                source,
                root / ".lmre",
                now=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
            )
            loaded = load_adopted_policy(root / ".lmre")
            self.assertIsInstance(loaded, AdoptedPolicy)
            self.assertEqual(loaded.policy_hash, adopted.policy_hash)
            self.assertEqual(
                loaded.adopted_at,
                "2026-07-30T18:00:00+00:00",
            )
            self.assertEqual(loaded.policy.policy_id, "local-managed-v1")

    def test_adopt_rejects_non_utc_clock(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "policy.json"
            source.write_text(json.dumps(_policy_document()), encoding="utf-8")
            with self.assertRaises(PolicyError):
                adopt_policy(
                    source,
                    root / ".lmre",
                    now=datetime(2026, 7, 30, 18, 0),
                )

    def test_tampered_adoption_record_fails_hash_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "policy.json"
            source.write_text(json.dumps(_policy_document()), encoding="utf-8")
            adopt_policy(source, root / ".lmre")
            record_path = root / ".lmre" / "operator-policy.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["policy"]["max_requests_per_run"] = 999
            record_path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(PolicyError) as context:
                load_adopted_policy(root / ".lmre")
            self.assertEqual(
                context.exception.code,
                "operator_policy_hash_mismatch",
            )

    def test_expired_policy_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(
                json.dumps(
                    _policy_document(expires_at="2026-07-30T17:59:59Z")
                ),
                encoding="utf-8",
            )
            with self.assertRaises(PolicyError) as context:
                load_policy(
                    path,
                    now=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
                )
            self.assertEqual(context.exception.code, "operator_policy_expired")

    def test_unknown_or_missing_fields_are_rejected(self) -> None:
        unknown = _policy_document(unexpected=True)
        with self.assertRaises(PolicyError):
            OperatorPolicy.from_dict(unknown)
        missing = _policy_document()
        del missing["policy_id"]
        with self.assertRaises(PolicyError):
            OperatorPolicy.from_dict(missing)

    def test_unsafe_authority_shapes_are_rejected(self) -> None:
        invalid_documents = (
            _policy_document(authorization_mode="per_run"),
            _policy_document(loopback_only=False),
            _policy_document(allowed_runtimes=["osaurus", "shell"]),
            _policy_document(reclaim_grace_seconds=30),
            _policy_document(allow_force_kill=True),
            _policy_document(allow_provider_edits=True),
            _policy_document(max_parallel_models=0),
            _policy_document(memory_floor_percent=0),
            _policy_document(max_run_minutes=0),
            _policy_document(max_requests_per_run=0),
            _policy_document(expires_at="2026-07-30T18:00:00-04:00"),
        )
        for document in invalid_documents:
            with self.subTest(document=document):
                with self.assertRaises(PolicyError):
                    OperatorPolicy.from_dict(document)

    def test_authorize_accepts_exact_limits(self) -> None:
        policy = OperatorPolicy.from_dict(_policy_document())
        authorize(policy, _request())

    def test_authorize_rejects_remote_endpoint(self) -> None:
        policy = OperatorPolicy.from_dict(_policy_document())
        with self.assertRaises(PolicyError) as context:
            authorize(
                policy,
                _request(endpoints=("https://example.com/v1",)),
            )
        self.assertEqual(context.exception.code, "operator_policy_denied")

    def test_authorize_rejects_each_limit_overage(self) -> None:
        policy = OperatorPolicy.from_dict(_policy_document())
        overages = (
            {"parallel_models": 2},
            {"memory_floor_percent": 19},
            {"estimated_minutes": 91},
            {"request_count": 251},
            {"runtimes": frozenset({"unknown"})},
        )
        for overage in overages:
            with self.subTest(overage=overage):
                with self.assertRaises(PolicyError) as context:
                    authorize(policy, _request(**overage))
                self.assertEqual(
                    context.exception.code,
                    "operator_policy_denied",
                )

    def test_authorize_rejects_capability_not_granted(self) -> None:
        cases = (
            ("allow_inference", {"inference": True}),
            ("allow_start", {"start": True}),
            ("allow_exact_reclaim", {"exact_reclaim": True}),
        )
        for policy_field, request_overrides in cases:
            with self.subTest(policy_field=policy_field):
                policy = OperatorPolicy.from_dict(
                    _policy_document(**{policy_field: False})
                )
                with self.assertRaises(PolicyError) as context:
                    authorize(policy, _request(**request_overrides))
                self.assertEqual(
                    context.exception.code,
                    "operator_policy_denied",
                )


if __name__ == "__main__":
    unittest.main()
