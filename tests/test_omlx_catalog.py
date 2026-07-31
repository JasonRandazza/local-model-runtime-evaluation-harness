from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.omlx_catalog import (
    OMLX_CATALOG_TOKEN,
    CatalogEntry,
    OmlxCatalogError,
    TemporaryOmlxCatalog,
)


class OmlxCatalogTests(unittest.TestCase):
    def test_catalog_links_only_authorized_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "weights"
            target.mkdir()
            catalog = TemporaryOmlxCatalog.create(
                root / "run" / "runtime" / "omlx-catalog",
                (CatalogEntry("model-a", target),),
            )
            link = catalog.path / "model-a"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), target.resolve())
            command = catalog.command(
                ("omlx", "serve", "--model-dir", OMLX_CATALOG_TOKEN),
            )
            self.assertEqual(command[-1], str(catalog.path))

    def test_cleanup_unlinks_catalog_without_deleting_target(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "weights"
            target.mkdir()
            marker = target / "config.json"
            marker.write_text("{}\n", encoding="utf-8")
            catalog = TemporaryOmlxCatalog.create(
                root / "catalog",
                (CatalogEntry("model-a", target),),
            )
            catalog.cleanup()
            self.assertTrue(target.is_dir())
            self.assertTrue(marker.is_file())
            self.assertFalse(catalog.path.exists())

    def test_missing_or_non_directory_target_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_target = root / "weights.bin"
            file_target.write_bytes(b"x")
            for target in (root / "missing", file_target):
                with self.subTest(target=target):
                    with self.assertRaises(OmlxCatalogError):
                        TemporaryOmlxCatalog.create(
                            root / f"catalog-{target.name}",
                            (CatalogEntry("model-a", target),),
                        )

    def test_unsafe_or_duplicate_model_ids_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "weights"
            target.mkdir()
            for model_id in ("../outside", "a/b", "", "a" * 129):
                with self.subTest(model_id=model_id):
                    with self.assertRaises(OmlxCatalogError):
                        TemporaryOmlxCatalog.create(
                            root / f"catalog-{len(model_id)}",
                            (CatalogEntry(model_id, target),),
                        )
            with self.assertRaises(OmlxCatalogError):
                TemporaryOmlxCatalog.create(
                    root / "duplicate",
                    (
                        CatalogEntry("model-a", target),
                        CatalogEntry("model-a", target),
                    ),
                )

    def test_preexisting_catalog_root_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "weights"
            target.mkdir()
            catalog = root / "catalog"
            catalog.mkdir()
            with self.assertRaises(OmlxCatalogError):
                TemporaryOmlxCatalog.create(
                    catalog,
                    (CatalogEntry("model-a", target),),
                )

    def test_command_requires_exactly_one_catalog_token(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "weights"
            target.mkdir()
            catalog = TemporaryOmlxCatalog.create(
                root / "catalog",
                (CatalogEntry("model-a", target),),
            )
            for command in (
                ("omlx", "serve"),
                (
                    "omlx",
                    "serve",
                    OMLX_CATALOG_TOKEN,
                    OMLX_CATALOG_TOKEN,
                ),
            ):
                with self.subTest(command=command):
                    with self.assertRaises(OmlxCatalogError):
                        catalog.command(command)

    def test_cleanup_rejects_foreign_non_symlink_entry(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "weights"
            target.mkdir()
            catalog = TemporaryOmlxCatalog.create(
                root / "catalog",
                (CatalogEntry("model-a", target),),
            )
            foreign = catalog.path / "foreign.txt"
            foreign.write_text("do not delete\n", encoding="utf-8")
            with self.assertRaises(OmlxCatalogError):
                catalog.cleanup()
            self.assertTrue(foreign.is_file())
            self.assertTrue(target.is_dir())

    def test_cleanup_rejects_retargeted_link(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            catalog = TemporaryOmlxCatalog.create(
                root / "catalog",
                (CatalogEntry("model-a", first),),
            )
            link = catalog.path / "model-a"
            link.unlink()
            link.symlink_to(second, target_is_directory=True)
            with self.assertRaises(OmlxCatalogError):
                catalog.cleanup()
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())


if __name__ == "__main__":
    unittest.main()
