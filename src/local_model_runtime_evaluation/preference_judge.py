"""Build judge prompts and parse blind pairwise preference responses."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .credentials import Credential
from .matrix_config import Cell
from .matrix_servers import ServerError, ServerHandle, build_server as default_build_server
from .preference_collect import resolve_credential
from .preference_config import PreferenceError, PreferenceSuite
from .preference_review import get_answer_content, load_answers
from .transport import LoopbackTransport, TransportError

DEFAULT_JUDGE_CELL: str = "jang_4m__osaurus"
REASON_MAX_CHARS: int = 500
JUDGE_MAX_TOKENS: int = 256

DEFAULT_READY_TIMEOUT_SECONDS = 180.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0

BuildServer = Callable[[Cell, LoopbackTransport, Path, Credential | None], ServerHandle]
TransportFactory = Callable[[set[str], int], LoopbackTransport]
CredentialFor = Callable[[str], Credential | None]

_VALID_WINNERS = frozenset({"A", "B", "tie"})


def build_judge_prompt(prompt_text: str, answer_a: str, answer_b: str) -> str:
    return (
        "You are judging two blind answers to the same prompt. "
        'Reply with ONLY a JSON object of the form '
        '{"winner":"A"|"B"|"tie","reason":"..."} '
        "with no other text.\n\n"
        f"Prompt:\n{prompt_text}\n\n"
        f"Answer A:\n{answer_a}\n\n"
        f"Answer B:\n{answer_b}\n"
    )


def _load_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        if start < 0:
            raise PreferenceError("judge response is not valid JSON")
        try:
            parsed, _ = json.JSONDecoder().raw_decode(stripped, start)
        except json.JSONDecodeError as exc:
            raise PreferenceError("judge response is not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise PreferenceError("judge response must be a JSON object")
    return parsed


def parse_judge_response(text: str) -> dict[str, str | None]:
    data = _load_json_object(text)
    winner = data.get("winner")
    if winner not in _VALID_WINNERS:
        raise PreferenceError("judge winner is invalid")

    reason: str | None = None
    if "reason" in data and data["reason"] is not None:
        reason = str(data["reason"])[:REASON_MAX_CHARS]

    return {"winner": winner, "reason": reason}


def _load_pairs(run_dir: Path) -> list[dict[str, str]]:
    pairs_path = run_dir / "pairs.json"
    if not pairs_path.is_file():
        raise PreferenceError(f"missing pairs file: {pairs_path}")
    payload = json.loads(pairs_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PreferenceError("pairs.json must be a JSON object")
    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise PreferenceError("pairs.json must contain a non-empty pairs list")
    required = {"pair_id", "prompt_id", "cell_a", "cell_b"}
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict) or not required.issubset(pair):
            raise PreferenceError(f"invalid pair at index {index}")
    return pairs  # type: ignore[return-value]


def _judge_pair(
    pair: dict[str, str],
    *,
    cell: Cell,
    prompts_by_id: dict[str, str],
    answers_by_cell: dict[str, dict[str, Any]],
    transport: LoopbackTransport,
    credential: Credential | None,
    cancel: threading.Event,
) -> tuple[dict[str, Any], dict[str, str | None]]:
    prompt_id = pair["prompt_id"]
    if prompt_id not in prompts_by_id:
        raise PreferenceError(f"unknown prompt_id {prompt_id!r}")
    prompt_text = prompts_by_id[prompt_id]
    answer_a = get_answer_content(answers_by_cell, pair["cell_a"], prompt_id)
    answer_b = get_answer_content(answers_by_cell, pair["cell_b"], prompt_id)
    judge_prompt = build_judge_prompt(prompt_text, answer_a, answer_b)

    attempts: list[dict[str, Any]] = []
    winner: str | None = None
    reason: str | None = None

    for _ in range(2):
        raw = ""
        try:
            result = transport.chat(
                cell.base_url,
                cell.model_id,
                judge_prompt,
                JUDGE_MAX_TOKENS,
                credential,
                cancel,
            )
            raw = result.content or ""
            parsed = parse_judge_response(raw)
            attempts.append({"raw": raw, "ok": True, "error": None})
            winner = parsed["winner"]  # type: ignore[assignment]
            reason = parsed["reason"]
            break
        except TransportError as error:
            attempts.append({"raw": raw, "ok": False, "error": str(error)})
        except PreferenceError as error:
            attempts.append({"raw": raw, "ok": False, "error": str(error)})

    return (
        {
            "pair_id": pair["pair_id"],
            "attempts": attempts,
            "winner": winner,
            "reason": reason,
        },
        {"pair_id": pair["pair_id"], "winner": winner, "reason": reason},
    )


def _merge_raw(run_dir: Path, judge_cell_id: str) -> None:
    raw_path = run_dir / "raw.json"
    raw: dict[str, Any] = {}
    if raw_path.is_file():
        loaded = json.loads(raw_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw = loaded
    raw["judge_cell_id"] = judge_cell_id
    raw["judged_at"] = datetime.now(timezone.utc).isoformat()
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_judge(
    run_dir: Path,
    *,
    judge_cell_id: str,
    cells_root: Path,
    suite: PreferenceSuite,
    build_server: BuildServer | None = None,
    transport_factory: TransportFactory | None = None,
    credential_for: CredentialFor | None = None,
    ready_timeout: float = DEFAULT_READY_TIMEOUT_SECONDS,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    cancel: threading.Event | None = None,
) -> Path:
    pairs = _load_pairs(run_dir)
    answers_by_cell = load_answers(run_dir)
    prompts_by_id = {prompt.prompt_id: prompt.prompt for prompt in suite.prompts}

    cell = Cell.load(cells_root / f"{judge_cell_id}.json")
    resolve = credential_for or (lambda server: resolve_credential(server))
    credential = resolve(cell.server)
    build = build_server or (
        lambda judge_cell, transport, log_dir, judge_credential: default_build_server(
            judge_cell, transport, log_dir, credential=judge_credential,
        )
    )
    make_transport = transport_factory or (
        lambda base_urls, timeout: LoopbackTransport(base_urls, timeout_seconds=timeout)
    )

    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    transport = make_transport({cell.base_url}, int(request_timeout))
    event = cancel or threading.Event()

    handle = build(cell, transport, log_dir, credential)
    try:
        handle.start()
        handle.wait_ready(cell.model_id, ready_timeout)
    except ServerError:
        try:
            handle.stop()
        except (ServerError, OSError, PermissionError):
            pass
        raise

    raw_pairs: list[dict[str, Any]] = []
    judgments: list[dict[str, str | None]] = []
    try:
        for pair in pairs:
            if event.is_set():
                break
            raw_pair, judgment = _judge_pair(
                pair,
                cell=cell,
                prompts_by_id=prompts_by_id,
                answers_by_cell=answers_by_cell,
                transport=transport,
                credential=credential,
                cancel=event,
            )
            raw_pairs.append(raw_pair)
            entry: dict[str, str | None] = {
                "pair_id": judgment["pair_id"],
                "winner": judgment["winner"],
            }
            if judgment["reason"] is not None:
                entry["reason"] = judgment["reason"]
            judgments.append(entry)
    finally:
        try:
            handle.stop()
        except (ServerError, OSError, PermissionError):
            pass

    judgments_payload = {"judgments": judgments}
    (run_dir / "judgments.json").write_text(
        json.dumps(judgments_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    judge_raw_payload = {"judge_cell_id": judge_cell_id, "pairs": raw_pairs}
    (run_dir / "judge_raw.json").write_text(
        json.dumps(judge_raw_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _merge_raw(run_dir, judge_cell_id)
    return run_dir
