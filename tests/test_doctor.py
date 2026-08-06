from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from local_model_runtime_evaluation import doctor
from local_model_runtime_evaluation.operator_policy import adopt_policy


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCTOR_SOURCE = REPO_ROOT / "src" / "local_model_runtime_evaluation" / "doctor.py"

# Every model-artifact template used by the real, active family configs
# (config/matrix/families/*.json). Building a machine profile whose roots
# contain these paths lets the "fully satisfied" tests exercise the real
# repository config read-only, since Campaign.load and run_identity's
# native-triple cross-check hardcode matrix_config.REPOSITORY_ROOT and
# cannot be redirected to a synthetic tree (see doctor.py's _diagnose_family
# docstring note).
_REAL_LOCAL_MODEL_DIRS = (
    "gemma-4-12B-it-qat-JANG_4M",
    "Ornith-1.0-35B-JANG_4M",
    "Qwen3.6-35B-A3B-JANGTQ4",
)
_REAL_HUGGINGFACE_DIRS = (
    "avneetsb/gemma-4-12B-it-qat-oQ4-fp16",
    "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
    "georgeis55/Ornith-1.0-35B-MLX-oQ4",
    "mlx-community/Ornith-1.0-35B-OptiQ-4bit",
    "Jundot/Qwen3.6-35B-A3B-oQ4-mtp",
    "mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit",
)

FIXED_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)

FORBIDDEN_MODULES = {
    "transport", "runtime_manager", "runtime_adapters", "process_inspection",
    "credentials", "resources", "matrix_lifecycle", "matrix_servers",
    "managed_run", "managed_run_cli", "subprocess", "socket", "http",
}


def _write_real_machine_profile(root: Path) -> Path:
    hf = root / "huggingface-hub"
    lm = root / "local-models"
    for name in _REAL_LOCAL_MODEL_DIRS:
        (lm / name).mkdir(parents=True, exist_ok=True)
    for name in _REAL_HUGGINGFACE_DIRS:
        (hf / name).mkdir(parents=True, exist_ok=True)
    profile = root / "machine-profile.json"
    profile.write_text(json.dumps({
        "schema_version": "1.0.0",
        "artifact_roots": {
            "huggingface_hub": str(hf),
            "local_models": str(lm),
        },
    }))
    return profile


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


def _adopt_valid_policy(root: Path, state_root: Path, *, now: datetime) -> None:
    source = root / "policy-source.json"
    source.write_text(json.dumps(_policy_document()))
    adopt_policy(source, state_root, now=now)


def _fake_which(*, found: tuple[str, ...] = ("osaurus", "omlx", "optiq")) -> object:
    def which(name: str) -> str | None:
        return f"/usr/local/bin/{name}" if name in found else None
    return which


def _write_family(root: Path, family_id: str, quants: dict[str, dict]) -> Path:
    families_dir = root / "config" / "matrix" / "families"
    families_dir.mkdir(parents=True, exist_ok=True)
    path = families_dir / f"{family_id}.json"
    path.write_text(json.dumps({"family_id": family_id, "quants": quants}))
    return path


def _write_recipe(root: Path, recipe_id: str) -> Path:
    recipes_dir = root / "config" / "managed-runs"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    path = recipes_dir / f"{recipe_id}.json"
    path.write_text(json.dumps({
        "schema_version": "1.0.0",
        "recipe_id": recipe_id,
        "steps": [
            "preflight", "matrix", "preference", "rag-oracle",
            "rag-keyword", "overhead", "seal",
        ],
        "matrix_mode": "screen",
        "estimated_minutes": 30,
        "memory_floor_percent": 20,
    }))
    return path


def _all_findings(result: dict) -> list[dict]:
    return [
        finding
        for section in result["sections"]
        for finding in section["findings"]
    ]


class DoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    # -- fully satisfied state (real repo config, synthetic profile/state) --

    def test_fully_satisfied_real_repo_is_offline_ready(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            which=_fake_which(),
            now=FIXED_NOW,
        )

        self.assertEqual(result["overall_readiness"], doctor.STATUS_OFFLINE_READY)
        self.assertEqual(result["actions"], [])
        findings = _all_findings(result)
        self.assertTrue(
            all(f["status"] != doctor.STATUS_ACTION_REQUIRED for f in findings)
        )
        live_checks = [f for f in findings if f["status"] == doctor.STATUS_NOT_CHECKED_LIVE]
        self.assertEqual(
            {f["check"] for f in live_checks},
            {
                "families.gemma-4-12b-qat.live_facts",
                "families.ornith-35b.live_facts",
                "families.qwen36-35b-a3b.live_facts",
            },
        )
        for f in live_checks:
            self.assertIn("endpoint reachability", f["summary"])
            self.assertIn("credentials", f["summary"])
            self.assertIn("memory headroom", f["summary"])
            self.assertIn("model load behavior", f["summary"])

        # JSON/text parity: every finding's status+check appears in the text.
        text = doctor.render_text(result)
        for f in findings:
            self.assertIn(f"[{f['status']}] {f['check']}", text)
        self.assertNotIn("live-ready", text.lower())

    def test_determinism_running_twice_is_identical(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        kwargs = dict(
            machine_profile_path=profile,
            state_root=state_root,
            which=_fake_which(),
            now=FIXED_NOW,
        )
        first = doctor.run_diagnostics(**kwargs)
        second = doctor.run_diagnostics(**kwargs)
        self.assertEqual(first, second)

    def test_missing_commands_is_action_required_and_deduped(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            which=_fake_which(found=()),
            now=FIXED_NOW,
        )
        self.assertEqual(result["overall_readiness"], doctor.STATUS_ACTION_REQUIRED)
        commands = next(s for s in result["sections"] if s["section"] == "commands")
        self.assertTrue(
            all(f["status"] == doctor.STATUS_ACTION_REQUIRED for f in commands["findings"])
        )
        families = next(s for s in result["sections"] if s["section"] == "families")
        per_family_findings = [
            f for f in families["findings"] if f["check"].endswith(".complete-native-quality-v1")
        ]
        self.assertEqual(len(per_family_findings), 3)
        self.assertTrue(all(f["status"] == doctor.STATUS_ACTION_REQUIRED for f in per_family_findings))
        # The shared families-section remediation must be deduplicated once.
        self.assertEqual(
            result["actions"].count("Resolve the listed issues, then re-run the doctor."),
            1,
        )

    # -- artifacts failure modes (real repo families, synthetic profile roots) --

    def test_missing_artifact_is_action_required(self) -> None:
        # Roots exist but are empty: none of the real family templates resolve
        # to an existing path.
        hf = self.root / "hf"
        lm = self.root / "lm"
        hf.mkdir()
        lm.mkdir()
        profile = self.root / "machine-profile.json"
        profile.write_text(json.dumps({
            "schema_version": "1.0.0",
            "artifact_roots": {"huggingface_hub": str(hf), "local_models": str(lm)},
        }))
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            which=_fake_which(),
            now=FIXED_NOW,
        )
        artifacts = next(s for s in result["sections"] if s["section"] == "artifacts")
        self.assertTrue(
            any(
                f["status"] == doctor.STATUS_ACTION_REQUIRED and "missing" in f["summary"]
                for f in artifacts["findings"]
            )
        )
        self.assertEqual(result["overall_readiness"], doctor.STATUS_ACTION_REQUIRED)

    def test_wrong_kind_artifact_is_action_required(self) -> None:
        profile_root = self.root / "machine"
        profile = _write_real_machine_profile(profile_root)
        roots = json.loads(profile.read_text())["artifact_roots"]
        target = Path(roots["local_models"]) / "gemma-4-12B-it-qat-JANG_4M"
        target.rmdir()
        target.write_text("not a model directory")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(
            f for f in _all_findings(result)
            if f["check"] == "artifacts.gemma-4-12b-qat.jang_4m"
        )
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("wrong kind", finding["summary"])

    def test_broken_symlink_artifact_is_action_required(self) -> None:
        # NOTE: artifact_profile.resolve_artifact_template calls Path.resolve()
        # on the templated path, which fully dereferences symlinks (verified:
        # a dangling symlink resolves to its target path with is_symlink()
        # False on the result). A broken symlink therefore cannot be observed
        # through the full family/cell .resolve(roots) pipeline; it always
        # surfaces as a plain "missing" finding instead (covered by
        # test_missing_artifact_is_action_required). This test instead
        # exercises doctor._artifact_path_status directly, the unit that
        # implements the design's broken-symlink branch, with a real dangling
        # symlink that has not been through Path.resolve().
        target = self.root / "dangling-link"
        target.symlink_to(self.root / "does-not-exist")
        status, summary, remediation = doctor._artifact_path_status(target)
        self.assertEqual(status, doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("broken symlink", summary)
        self.assertIsNotNone(remediation)

    def test_unreadable_artifact_is_action_required(self) -> None:
        profile_root = self.root / "machine"
        profile = _write_real_machine_profile(profile_root)
        roots = json.loads(profile.read_text())["artifact_roots"]
        local_models = Path(roots["local_models"])
        target = local_models / "gemma-4-12B-it-qat-JANG_4M"
        os.chmod(target, 0o000)
        self.addCleanup(os.chmod, target, 0o700)
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(
            f for f in _all_findings(result)
            if f["check"] == "artifacts.gemma-4-12b-qat.jang_4m"
        )
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("unreadable", finding["summary"])

    def test_artifact_template_escape_is_reported_via_artifact_profile_error(self) -> None:
        # Synthetic repository_root: artifacts only depends on family loading
        # (family.resolve(roots)), not on Campaign, so this is fully
        # synthetic-tree testable.
        _write_family(self.root, "escape-family", {
            "q1": {
                "artifact_path": "{LMRE_ROOT:local_models}/../escape",
                "model_ids": ["m1"],
                "native_server": "osaurus",
            },
        })
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            repository_root=self.root,
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(
            f for f in _all_findings(result) if f["check"] == "artifacts.escape-family"
        )
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("template", finding["detail"] or "")

    # -- machine profile failure modes --

    def test_machine_profile_missing_file(self) -> None:
        result = doctor.run_diagnostics(
            machine_profile_path=self.root / "does-not-exist.json",
            state_root=self.root / "state",
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "machine_profile.roots")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)

    def test_machine_profile_malformed_json(self) -> None:
        path = self.root / "machine-profile.json"
        path.write_text("{not valid json")
        result = doctor.run_diagnostics(
            machine_profile_path=path,
            state_root=self.root / "state",
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "machine_profile.roots")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)

    def test_machine_profile_wrong_schema_version(self) -> None:
        path = self.root / "machine-profile.json"
        path.write_text(json.dumps({
            "schema_version": "9.9.9",
            "artifact_roots": {"huggingface_hub": "/tmp", "local_models": "/tmp"},
        }))
        result = doctor.run_diagnostics(
            machine_profile_path=path,
            state_root=self.root / "state",
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "machine_profile.roots")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)

    def test_machine_profile_wrong_root_keys(self) -> None:
        path = self.root / "machine-profile.json"
        path.write_text(json.dumps({
            "schema_version": "1.0.0",
            "artifact_roots": {"wrong_key": "/tmp"},
        }))
        result = doctor.run_diagnostics(
            machine_profile_path=path,
            state_root=self.root / "state",
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "machine_profile.roots")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)

    def test_machine_profile_nonexistent_root(self) -> None:
        path = self.root / "machine-profile.json"
        path.write_text(json.dumps({
            "schema_version": "1.0.0",
            "artifact_roots": {
                "huggingface_hub": str(self.root / "nowhere-hf"),
                "local_models": str(self.root / "nowhere-lm"),
            },
        }))
        result = doctor.run_diagnostics(
            machine_profile_path=path,
            state_root=self.root / "state",
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "machine_profile.roots")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)

    def test_machine_profile_broken_link_root(self) -> None:
        broken = self.root / "broken-root"
        broken.symlink_to(self.root / "nowhere")
        path = self.root / "machine-profile.json"
        path.write_text(json.dumps({
            "schema_version": "1.0.0",
            "artifact_roots": {
                "huggingface_hub": str(broken),
                "local_models": str(broken),
            },
        }))
        result = doctor.run_diagnostics(
            machine_profile_path=path,
            state_root=self.root / "state",
            which=_fake_which(),
            now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "machine_profile.roots")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)

    # -- policy states --

    def test_policy_valid(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)
        result = doctor.run_diagnostics(
            machine_profile_path=profile, state_root=state_root,
            which=_fake_which(), now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "policy.adopted")
        self.assertEqual(finding["status"], doctor.STATUS_OFFLINE_READY)
        self.assertIn("policy_id=local-managed-v1", finding["detail"])

    def test_policy_absent(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        result = doctor.run_diagnostics(
            machine_profile_path=profile, state_root=self.root / "state",
            which=_fake_which(), now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "policy.adopted")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("operator_policy_missing", finding["detail"])

    def test_policy_expired(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        adopted_at = FIXED_NOW
        expires_at = datetime(2026, 8, 5, 13, 0, tzinfo=timezone.utc)
        source = self.root / "policy-source.json"
        source.write_text(json.dumps(_policy_document(
            expires_at=expires_at.isoformat().replace("+00:00", "Z"),
        )))
        adopt_policy(source, state_root, now=adopted_at)
        later = datetime(2026, 8, 6, tzinfo=timezone.utc)
        result = doctor.run_diagnostics(
            machine_profile_path=profile, state_root=state_root,
            which=_fake_which(), now=later,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "policy.adopted")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("operator_policy_expired", finding["detail"])

    def test_policy_hash_mismatch(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)
        adopted_path = state_root / "operator-policy.json"
        body = json.loads(adopted_path.read_text())
        body["policy_hash"] = "0" * 64
        adopted_path.write_text(json.dumps(body))
        result = doctor.run_diagnostics(
            machine_profile_path=profile, state_root=state_root,
            which=_fake_which(), now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "policy.adopted")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("operator_policy_hash_mismatch", finding["detail"])

    def test_policy_malformed(self) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        state_root.mkdir(parents=True)
        (state_root / "operator-policy.json").write_text("not json")
        result = doctor.run_diagnostics(
            machine_profile_path=profile, state_root=state_root,
            which=_fake_which(), now=FIXED_NOW,
        )
        finding = next(f for f in _all_findings(result) if f["check"] == "policy.adopted")
        self.assertEqual(finding["status"], doctor.STATUS_ACTION_REQUIRED)

    # -- configuration failure isolation --

    def test_one_malformed_family_hides_nothing_else(self) -> None:
        _write_family(self.root, "good-family", {
            "q1": {
                "artifact_path": "{LMRE_ROOT:local_models}/good-model",
                "model_ids": ["m1"],
                "native_server": "osaurus",
            },
        })
        bad_path = self.root / "config" / "matrix" / "families" / "bad-family.json"
        bad_path.write_text("{ this is not valid json")
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            repository_root=self.root,
            which=_fake_which(),
            now=FIXED_NOW,
        )
        configuration = next(s for s in result["sections"] if s["section"] == "configuration")
        bad_finding = next(
            f for f in configuration["findings"] if f["check"] == "configuration.family.bad-family"
        )
        good_finding = next(
            f for f in configuration["findings"] if f["check"] == "configuration.family.good-family"
        )
        self.assertEqual(bad_finding["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertIn("family:", bad_finding["detail"])
        # good-family's own load succeeded; whatever else fails for it (e.g.
        # a missing campaign file) is not reported as a "family:" problem.
        self.assertNotIn("family:", good_finding["detail"] or "")

    def test_pathologically_nested_family_json_degrades_one_finding(self) -> None:
        # RecursionError from json.loads must become one ACTION_REQUIRED
        # finding, not abort the diagnostic (review-wave regression).
        synthetic = self.root / "repo"
        _write_recipe(synthetic, "recipe-one")
        families_dir = synthetic / "config" / "matrix" / "families"
        families_dir.mkdir(parents=True, exist_ok=True)
        depth = 200_000
        (families_dir / "bad-family.json").write_text(
            "[" * depth + "]" * depth
        )
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            repository_root=synthetic,
            which=_fake_which(),
            now=FIXED_NOW,
        )

        findings = {
            finding["check"]: finding for finding in _all_findings(result)
        }
        self.assertEqual(
            findings["configuration.family.bad-family"]["status"],
            doctor.STATUS_ACTION_REQUIRED,
        )
        # Unrelated sections stayed visible.
        self.assertIn("policy.adopted", findings)
        self.assertIn("configuration.recipe.recipe-one", findings)

    def test_empty_config_tree_fails_closed(self) -> None:
        # A gutted install (no recipes, no families) must not aggregate to
        # OFFLINE_READY on harness checks alone.
        empty_root = self.root / "empty-repo"
        empty_root.mkdir()
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            repository_root=empty_root,
            which=_fake_which(),
            now=FIXED_NOW,
        )

        self.assertEqual(
            result["overall_readiness"], doctor.STATUS_ACTION_REQUIRED
        )
        checks = {finding["check"] for finding in _all_findings(result)}
        self.assertIn("configuration.recipes", checks)
        self.assertIn("configuration.families", checks)

    def test_harness_missing_bin_and_docs(self) -> None:
        # A bare synthetic repository_root has neither bin/ wrappers nor docs.
        profile = _write_real_machine_profile(self.root / "machine")
        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=self.root / "state",
            repository_root=self.root / "bare-repo",
            which=_fake_which(),
            now=FIXED_NOW,
        )
        harness = next(s for s in result["sections"] if s["section"] == "harness")
        bins = next(f for f in harness["findings"] if f["check"] == "harness.bin_wrappers")
        docs = next(f for f in harness["findings"] if f["check"] == "harness.docs")
        self.assertEqual(bins["status"], doctor.STATUS_ACTION_REQUIRED)
        self.assertEqual(docs["status"], doctor.STATUS_ACTION_REQUIRED)

    # -- tripwires --

    @patch("os.kill", side_effect=AssertionError("os.kill touched"))
    @patch("subprocess.call", side_effect=AssertionError("subprocess.call touched"))
    @patch("subprocess.run", side_effect=AssertionError("subprocess.run touched"))
    @patch("subprocess.Popen", side_effect=AssertionError("subprocess.Popen touched"))
    @patch("socket.socket", side_effect=AssertionError("socket.socket touched"))
    def test_tripwire_no_live_contact_during_full_diagnostic(self, *_mocks: object) -> None:
        profile = _write_real_machine_profile(self.root / "machine")
        state_root = self.root / "state"
        _adopt_valid_policy(self.root, state_root, now=FIXED_NOW)

        result = doctor.run_diagnostics(
            machine_profile_path=profile,
            state_root=state_root,
            which=_fake_which(),
            now=FIXED_NOW,
        )
        self.assertEqual(result["overall_readiness"], doctor.STATUS_OFFLINE_READY)

    def test_static_scan_has_no_forbidden_imports(self) -> None:
        tree = ast.parse(DOCTOR_SOURCE.read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in FORBIDDEN_MODULES:
                        found.add(top)
            elif isinstance(node, ast.ImportFrom) and node.module:
                for part in node.module.split("."):
                    if part in FORBIDDEN_MODULES:
                        found.add(part)
        self.assertEqual(found, set())

    def test_fresh_import_never_pulls_forbidden_modules(self) -> None:
        script = (
            "import sys\n"
            "import local_model_runtime_evaluation.doctor\n"
            "forbidden = " + repr(sorted(FORBIDDEN_MODULES)) + "\n"
            "hits = sorted(\n"
            "    name for name in sys.modules\n"
            "    if any(name == 'local_model_runtime_evaluation.' + f for f in forbidden)\n"
            ")\n"
            "print(hits)\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
