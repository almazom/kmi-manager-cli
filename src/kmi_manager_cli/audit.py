from __future__ import annotations

import os

from kmi_manager_cli.logging import log_event


def current_actor() -> str:
    for key in ("KMI_AUDIT_ACTOR", "USER", "USERNAME"):
        value = os.getenv(key)
        if value:
            return value
    return "unknown"


def log_audit_event(logger, action: str, **fields) -> None:
    log_event(logger, "audit_event", action=action, actor=current_actor(), **fields)
