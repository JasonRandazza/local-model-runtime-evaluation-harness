"""Parser registration and command handler for the ruling surface.

`add_ruling_parser` registers a top-level `ruling` command with its own
sub-subcommands, mirroring how the CLI already nests `policy show` / `policy adopt`.
`command_ruling` returns the JSON body the caller prints. A bad rubric is an
operator error and lets `RubricError` escape untouched; an unrulable bundle is a
conclusion and is reported honestly rather than raised as a failure.

Contact nothing: no network, model, runtime, or credential store.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .ruling import UNAVAILABLE, build_ruling
from .rubric import Rubric
from .ruling_store import list_rulings, save_ruling

DEFAULT_RULINGS_DIR = Path("results/rulings")


def add_ruling_parser(commands) -> None:
    ruling = commands.add_parser(
        "ruling", help="Draw and read conclusions over sealed evidence"
    )
    ruling_commands = ruling.add_subparsers(dest="ruling_command", required=True)

    make = ruling_commands.add_parser("make", help="Rule a sealed run under a rubric")
    make.add_argument("--run", type=Path, required=True, help="sealed run directory to rule over")
    make.add_argument("--rubric", type=Path, required=True, help="rubric file to rule under")
    make.add_argument(
        "--rulings-root", type=Path, default=DEFAULT_RULINGS_DIR,
        help="directory rulings are written to and read from",
    )

    listing = ruling_commands.add_parser("list", help="List saved rulings as an index")
    listing.add_argument(
        "--rulings-root", type=Path, default=DEFAULT_RULINGS_DIR,
        help="directory the listing is read from",
    )


def command_ruling(args: argparse.Namespace) -> dict:
    if args.ruling_command == "make":
        return _command_make(args)
    if args.ruling_command == "list":
        return _command_list(args)
    raise ValueError(f"unknown ruling command {args.ruling_command!r}")


def _command_make(args: argparse.Namespace) -> dict:
    rubric = Rubric.load(args.rubric)
    ruling = build_ruling(args.run, rubric)

    if ruling["outcome"]["state"] == UNAVAILABLE:
        return {"ok": True, "saved": False, "path": None, "ruling": ruling}

    path = save_ruling(args.rulings_root, ruling)
    return {"ok": True, "saved": True, "path": str(path), "ruling": ruling}


def _command_list(args: argparse.Namespace) -> dict:
    rulings = list_rulings(args.rulings_root)
    entries = [
        {
            "ruling_id": entry["ruling_id"],
            "created_at": entry["created_at"],
            "run_id": entry["run_id"],
            "path": entry["path"],
            "superseded_by": entry["superseded_by"],
        }
        for entry in rulings
    ]
    return {"ok": True, "rulings_root": str(args.rulings_root), "rulings": entries}
