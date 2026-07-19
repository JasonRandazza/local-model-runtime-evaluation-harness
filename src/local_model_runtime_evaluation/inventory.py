from __future__ import annotations

import platform
import shutil
import sys


def collect_inventory() -> dict[str, object]:
    commands: dict[str, dict[str, object]] = {}
    for name in ("osaurus", "optiq", "python3", "swift"):
        path = shutil.which(name)
        commands[name] = {"present": path is not None, "path": path}
    return {
        "collection_mode": "passive_path_lookup",
        "commands": commands,
        "host": {
            "platform": platform.system(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "network_calls_attempted": 0,
        "processes_started": 0,
    }
