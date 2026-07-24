from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DISCOVERY_SCHEMA_VERSION = "1.0.0"
CONFIRM_POLICY_EXPLICIT = "explicit_execute"

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DISCOVERY_RESULTS_ROOT = REPOSITORY_ROOT / "results" / "discovery"


class DiscoveryError(Exception):
    pass


def proposal_content_hash(body: dict[str, object]) -> str:
    payload = {k: v for k, v in sorted(body.items()) if k != "content_hash"}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def allocate_proposal_id(results_root: Path, *, now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    prefix = f"discovery-{date_str}-"
    max_seq = 0
    if results_root.exists():
        for entry in results_root.iterdir():
            if not entry.is_dir() or not entry.name.startswith(prefix):
                continue
            suffix = entry.name[len(prefix) :]
            if len(suffix) == 3 and suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:03d}"


def write_proposal(results_root: Path, proposal: dict[str, object]) -> Path:
    if "proposal_id" not in proposal:
        raise DiscoveryError("proposal_id is required")
    proposal_id = proposal["proposal_id"]
    if not isinstance(proposal_id, str):
        raise DiscoveryError("proposal_id must be a string")
    body = dict(proposal)
    body["content_hash"] = proposal_content_hash(body)
    proposal_dir = results_root / proposal_id
    proposal_dir.mkdir(parents=True, exist_ok=False)
    path = proposal_dir / "proposal.json"
    path.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_proposal(results_root: Path, proposal_id: str) -> dict[str, object]:
    path = results_root / proposal_id / "proposal.json"
    if not path.is_file():
        raise DiscoveryError(f"proposal not found: {proposal_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_proposal_hash(proposal: dict[str, object]) -> None:
    stored = proposal.get("content_hash")
    if not isinstance(stored, str) or not stored:
        raise DiscoveryError("content_hash missing or invalid")
    expected = proposal_content_hash(proposal)
    if stored != expected:
        raise DiscoveryError("content_hash mismatch")


def write_execution(proposal_dir: Path, execution: dict[str, object]) -> Path:
    path = proposal_dir / "execution.json"
    path.write_text(
        json.dumps(execution, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
