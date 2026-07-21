from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.artifacts import ArtifactBundle
from local_model_runtime_evaluation.post_attempt_journal import (
    PostAttemptJournal,
    PostAttemptPhase,
)


class PostAttemptJournalTest(unittest.TestCase):
    def _journal(self, path: Path) -> PostAttemptJournal:
        return PostAttemptJournal(ArtifactBundle(path))

    def test_conservative_count_includes_dispatched_without_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            journal = self._journal(Path(temp))
            journal.record(
                sequence=1, phase=PostAttemptPhase.PREPARED,
                workload_id="short-chat", route="direct",
            )
            journal.record(
                sequence=1, phase=PostAttemptPhase.DISPATCHED,
                workload_id="short-chat", route="direct",
            )
            self.assertEqual(journal.conservative_post_count(), 1)

    def test_prepared_only_does_not_count_as_sent_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            journal = self._journal(Path(temp))
            journal.record(
                sequence=1, phase=PostAttemptPhase.PREPARED,
                workload_id="short-chat", route="direct",
            )
            self.assertEqual(journal.conservative_post_count(), 0)

    def test_completed_and_failed_both_count_once_per_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            journal = self._journal(Path(temp))
            for sequence, phase in (
                (1, PostAttemptPhase.PREPARED), (1, PostAttemptPhase.DISPATCHED),
                (1, PostAttemptPhase.COMPLETED),
                (2, PostAttemptPhase.PREPARED), (2, PostAttemptPhase.DISPATCHED),
                (2, PostAttemptPhase.FAILED),
            ):
                journal.record(
                    sequence=sequence, phase=phase, workload_id="short-chat", route="direct",
                )
            self.assertEqual(journal.conservative_post_count(), 2)

    def test_count_is_read_fresh_from_disk_across_journal_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            bundle = ArtifactBundle(path)
            first = PostAttemptJournal(bundle)
            first.record(
                sequence=1, phase=PostAttemptPhase.PREPARED,
                workload_id="short-chat", route="direct",
            )
            first.record(
                sequence=1, phase=PostAttemptPhase.DISPATCHED,
                workload_id="short-chat", route="direct",
            )
            second = PostAttemptJournal(bundle)
            self.assertEqual(second.conservative_post_count(), 1)

    def test_missing_journal_file_counts_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            journal = self._journal(Path(temp))
            self.assertEqual(journal.conservative_post_count(), 0)

    def test_record_writes_sanitized_append_only_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            journal = self._journal(path)
            journal.record(
                sequence=3, phase=PostAttemptPhase.DISPATCHED,
                workload_id="structured-tool-json", route="routed", detail="dispatched",
            )
            lines = (path / "post-attempts.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["sequence"], 3)
            self.assertEqual(record["phase"], "dispatched")
            self.assertEqual(record["workload_id"], "structured-tool-json")
            self.assertEqual(record["route"], "routed")
            self.assertEqual(record["detail"], "dispatched")
            self.assertNotIn("prompt", record)

    def test_failed_detail_allowlist_and_http_status_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            journal = self._journal(path)
            journal.record(
                sequence=1, phase=PostAttemptPhase.FAILED,
                workload_id="short-chat", route="direct",
                detail="incomplete_sse",
            )
            journal.record(
                sequence=2, phase=PostAttemptPhase.FAILED,
                workload_id="short-chat", route="direct",
                detail="http_status", http_status=503,
            )
            journal.record(
                sequence=3, phase=PostAttemptPhase.FAILED,
                workload_id="short-chat", route="direct",
                detail="Authorization=secret leaked body",
                http_status=999,
            )
            rows = [
                json.loads(line)
                for line in (path / "post-attempts.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(rows[0]["detail"], "incomplete_sse")
            self.assertEqual(rows[1]["detail"], "http_status")
            self.assertEqual(rows[1]["http_status"], 503)
            self.assertEqual(rows[2]["detail"], "transport_failed")
            self.assertNotIn("http_status", rows[2])
            self.assertNotIn("Authorization", json.dumps(rows))


if __name__ == "__main__":
    unittest.main()
