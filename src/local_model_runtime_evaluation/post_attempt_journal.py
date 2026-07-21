from __future__ import annotations

import json
from enum import Enum

from .artifacts import ArtifactBundle

_FILENAME = "post-attempts.jsonl"


class PostAttemptPhase(str, Enum):
    PREPARED = "prepared"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"


_DISPATCHED_OR_LATER = {
    PostAttemptPhase.DISPATCHED, PostAttemptPhase.COMPLETED, PostAttemptPhase.FAILED,
}


class PostAttemptJournal:
    """Durable, append-only record of POST-attempt phases.

    Crash-consistent authority for "was a POST possibly sent": counting is
    read fresh from disk on every call so a fresh instance recovering after a
    crash reports the same conservative count as the instance that recorded
    it.
    """

    def __init__(self, bundle: ArtifactBundle) -> None:
        self._bundle = bundle

    def record(
        self,
        *,
        sequence: int,
        phase: PostAttemptPhase,
        workload_id: str,
        route: str,
        detail: str | None = None,
    ) -> None:
        record: dict[str, object] = {
            "sequence": sequence,
            "phase": phase.value,
            "workload_id": workload_id,
            "route": route,
        }
        if detail is not None:
            record["detail"] = detail
        self._bundle.append_jsonl(_FILENAME, record)

    def _read_records(self) -> list[dict[str, object]]:
        try:
            text = (self._bundle.path / _FILENAME).read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        records: list[dict[str, object]] = []
        for line in text.splitlines():
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                # A corrupted trailing line could hide a real dispatch; fail
                # closed by treating it as a possible POST rather than
                # silently dropping it from the count.
                records.append({"sequence": None, "phase": None})
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def conservative_post_count(self) -> int:
        """Count sequences that reached DISPATCHED or later.

        Never underreports: unparseable rows and unrecognized phase values
        are treated as a possible dispatch rather than ignored.
        """
        counted: set[object] = set()
        unattributed = 0
        for record in self._read_records():
            sequence = record.get("sequence")
            raw_phase = record.get("phase")
            try:
                phase = PostAttemptPhase(raw_phase)
            except ValueError:
                if sequence is not None:
                    counted.add(sequence)
                else:
                    unattributed += 1
                continue
            if phase in _DISPATCHED_OR_LATER:
                if sequence is not None:
                    counted.add(sequence)
                else:
                    unattributed += 1
        return len(counted) + unattributed
