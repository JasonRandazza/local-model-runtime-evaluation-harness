from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.artifact_profile import (
    ArtifactProfileError,
    load_artifact_roots,
    resolve_artifact_template,
    resolve_artifact_text,
)
from tests.artifact_profile_fixtures import temporary_machine_profile


class ArtifactProfileTests(unittest.TestCase):
    def test_loads_exact_absolute_directory_roots(self) -> None:
        with temporary_machine_profile() as (profile, expected):
            roots = load_artifact_roots(profile)

        self.assertEqual(roots.huggingface_hub, expected["huggingface_hub"].resolve())
        self.assertEqual(roots.local_models, expected["local_models"].resolve())

    def test_rejects_unknown_or_missing_profile_fields(self) -> None:
        with temporary_machine_profile() as (profile, _):
            body = json.loads(profile.read_text(encoding="utf-8"))
            for changed in (
                {"schema_version": "1.0.0"},
                {**body, "unexpected": True},
                {**body, "schema_version": "2.0.0"},
            ):
                with self.subTest(changed=changed):
                    profile.write_text(json.dumps(changed), encoding="utf-8")
                    with self.assertRaises(ArtifactProfileError):
                        load_artifact_roots(profile)
                    profile.write_text(json.dumps(body), encoding="utf-8")

    def test_rejects_unknown_or_missing_root_keys(self) -> None:
        with temporary_machine_profile() as (profile, expected):
            bodies = (
                {"local_models": str(expected["local_models"])},
                {
                    **{key: str(value) for key, value in expected.items()},
                    "extra": str(expected["local_models"]),
                },
            )
            for roots in bodies:
                with self.subTest(roots=roots):
                    profile.write_text(
                        json.dumps(
                            {
                                "schema_version": "1.0.0",
                                "artifact_roots": roots,
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ArtifactProfileError):
                        load_artifact_roots(profile)

    def test_rejects_relative_tilde_missing_and_file_roots(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "valid"
            valid.mkdir()
            file_root = root / "file"
            file_root.write_text("not a directory", encoding="utf-8")
            cases = ("relative/path", "~/models", str(root / "missing"), str(file_root))
            for invalid in cases:
                with self.subTest(invalid=invalid):
                    profile = root / "profile.json"
                    profile.write_text(
                        json.dumps(
                            {
                                "schema_version": "1.0.0",
                                "artifact_roots": {
                                    "huggingface_hub": str(valid),
                                    "local_models": invalid,
                                },
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ArtifactProfileError):
                        load_artifact_roots(profile)

    def test_rejects_broken_symlink_root(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "valid"
            valid.mkdir()
            broken = root / "broken"
            broken.symlink_to(root / "missing", target_is_directory=True)
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "artifact_roots": {
                            "huggingface_hub": str(valid),
                            "local_models": str(broken),
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ArtifactProfileError):
                load_artifact_roots(profile)

    def test_resolves_only_approved_leading_root_templates(self) -> None:
        with temporary_machine_profile() as (profile, expected):
            roots = load_artifact_roots(profile)
            resolved = resolve_artifact_template(
                "{LMRE_ROOT:huggingface_hub}/mlx-community/model-a",
                roots,
            )

        self.assertEqual(
            resolved,
            str((expected["huggingface_hub"] / "mlx-community" / "model-a").resolve()),
        )

    def test_rejects_unsafe_or_unknown_artifact_templates(self) -> None:
        with temporary_machine_profile() as (profile, _):
            roots = load_artifact_roots(profile)
            cases = (
                "/absolute/model",
                "model-without-root-token",
                "prefix/{LMRE_ROOT:local_models}/model",
                "{LMRE_ROOT:unknown}/model",
                "{LMRE_ROOT:local_models}/",
                "{LMRE_ROOT:local_models}/../escape",
                "{LMRE_ROOT:local_models}/./model",
                "{LMRE_ROOT:local_models}//absolute",
                "{LMRE_ROOT:local_models}/folder\\model",
                "{LMRE_ROOT:local_models}/{unknown}",
            )
            for template in cases:
                with self.subTest(template=template):
                    with self.assertRaises(ArtifactProfileError):
                        resolve_artifact_template(template, roots)

    def test_resolves_only_the_exact_artifact_path_token_in_text(self) -> None:
        artifact = "/synthetic/models/model-a"
        self.assertEqual(
            resolve_artifact_text("{artifact_path}:no-think", artifact),
            "/synthetic/models/model-a:no-think",
        )
        self.assertEqual(
            resolve_artifact_text("optiq/{artifact_path}:think", artifact),
            "optiq//synthetic/models/model-a:think",
        )
        self.assertEqual(resolve_artifact_text("fixed-id", artifact), "fixed-id")

    def test_rejects_unknown_or_unresolved_text_tokens(self) -> None:
        for value in ("{artifact}", "{LMRE_ROOT:local_models}/model", "left}", "{right"):
            with self.subTest(value=value):
                with self.assertRaises(ArtifactProfileError):
                    resolve_artifact_text(value, "/synthetic/models/model-a")

    def test_preserves_only_explicitly_allowlisted_non_artifact_token(self) -> None:
        self.assertEqual(
            resolve_artifact_text(
                "{LMRE_OMLX_CATALOG}",
                "/synthetic/models/model-a",
                allowed_tokens=frozenset({"{LMRE_OMLX_CATALOG}"}),
            ),
            "{LMRE_OMLX_CATALOG}",
        )
        with self.assertRaises(ArtifactProfileError):
            resolve_artifact_text(
                "{unknown}",
                "/synthetic/models/model-a",
                allowed_tokens=frozenset({"{LMRE_OMLX_CATALOG}"}),
            )


if __name__ == "__main__":
    unittest.main()
