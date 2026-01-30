from __future__ import annotations

import os
import stat
from pathlib import Path

from kmi_manager_cli.logging import log_event


def is_insecure_permissions(path: Path) -> bool:
    if os.name == "nt":
        return False
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return False
    return bool(mode & (stat.S_IRWXG | stat.S_IRWXO))


def warn_if_insecure(path: Path, logger, label: str) -> None:
    if is_insecure_permissions(path):
        log_event(logger, "insecure_permissions", path=str(path), label=label)
