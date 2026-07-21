from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.locking import LockError, RunLock


class LockingTest(unittest.TestCase):
    def test_owner_is_none_without_a_lock_and_does_not_create_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))

            self.assertIsNone(lock.owner())
            self.assertFalse(lock.path.exists())

    def test_owner_returns_exact_acquired_run_id_without_modifying_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            lock.acquire("stage2-20260715-901")
            before = lock.path.read_bytes()

            self.assertEqual(lock.owner(), "stage2-20260715-901")
            self.assertEqual(lock.path.read_bytes(), before)

    def test_owner_returns_stripped_competing_run_without_releasing_or_modifying_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            lock.path.parent.mkdir(parents=True, exist_ok=True)
            lock.path.write_text("  stage2-20260715-902  \n", encoding="utf-8")
            before = lock.path.read_bytes()

            self.assertEqual(lock.owner(), "stage2-20260715-902")
            self.assertTrue(lock.path.exists())
            self.assertEqual(lock.path.read_bytes(), before)

    def test_owner_returns_none_for_whitespace_only_lock_without_modifying_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            lock.path.parent.mkdir(parents=True, exist_ok=True)
            lock.path.write_text(" \n\t", encoding="utf-8")
            before = lock.path.read_bytes()

            self.assertIsNone(lock.owner())
            self.assertTrue(lock.path.exists())
            self.assertEqual(lock.path.read_bytes(), before)

    def test_lock_rejects_competing_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            lock.acquire("stage0-20260713-001")
            with self.assertRaises(LockError):
                lock.acquire("stage0-20260713-002")
            with self.assertRaises(LockError):
                lock.release("stage0-20260713-002")
            lock.release("stage0-20260713-001")

    def test_release_fails_when_lock_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            lock.acquire("run-a")
            lock.path.unlink()
            with self.assertRaises(LockError):
                lock.release("run-a")

    def test_assert_owner_fails_when_lock_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            with self.assertRaises(LockError):
                lock.assert_owner("run-a")

    def test_assert_owner_fails_when_lock_owner_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            lock.acquire("run-a")
            lock.path.write_text("run-b\n", encoding="utf-8")
            with self.assertRaises(LockError):
                lock.assert_owner("run-a")

    def test_assert_owner_succeeds_without_modifying_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = RunLock(Path(temp))
            lock.acquire("run-a")
            before = lock.path.read_bytes()
            lock.assert_owner("run-a")
            self.assertEqual(lock.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
