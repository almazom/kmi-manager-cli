from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from kmi_manager_cli.config import Config
from kmi_manager_cli.keys import Registry
from kmi_manager_cli.locking import atomic_write_text, file_lock
from kmi_manager_cli.logging import get_logger
from kmi_manager_cli.security import warn_if_insecure

STATE_SCHEMA_VERSION = 1


@dataclass
class KeyState:
    last_used: Optional[str] = None
    request_count: int = 0
    error_401: int = 0
    error_403: int = 0
    error_429: int = 0
    error_5xx: int = 0
    exhausted_until: Optional[str] = None


@dataclass
class State:
    schema_version: int = STATE_SCHEMA_VERSION
    active_index: int = 0
    rotation_index: int = 0
    auto_rotate: bool = False
    keys: dict[str, KeyState] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "active_index": self.active_index,
            "rotation_index": self.rotation_index,
            "auto_rotate": self.auto_rotate,
            "keys": {label: vars(state) for label, state in self.keys.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        schema_version = int(data.get("schema_version", STATE_SCHEMA_VERSION))
        keys = {label: KeyState(**info) for label, info in data.get("keys", {}).items()}
        return cls(
            schema_version=schema_version,
            active_index=int(data.get("active_index", 0)),
            rotation_index=int(data.get("rotation_index", 0)),
            auto_rotate=bool(data.get("auto_rotate", False)),
            keys=keys,
        )


def _state_path(config: Config) -> Path:
    return config.state_dir.expanduser() / "state.json"


def load_state(config: Config, registry: Registry) -> State:
    config.state_dir.expanduser().mkdir(parents=True, exist_ok=True)
    path = _state_path(config)
    logger = get_logger(config)
    warn_if_insecure(config.state_dir.expanduser(), logger, "state_dir")
    if path.exists():
        warn_if_insecure(path, logger, "state_file")

    changed = False
    if path.exists():
        with file_lock(path):
            try:
                data = json.loads(path.read_text())
                state = State.from_dict(data)
            except json.JSONDecodeError:
                corrupt = path.with_suffix(path.suffix + f".corrupt.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
                path.rename(corrupt)
                state = State()
                changed = True
    else:
        state = State()
        changed = True

    # Ensure keys exist in state
    for key in registry.keys:
        if key.label not in state.keys:
            state.keys[key.label] = KeyState()
            changed = True

    # Clamp active index to registry size
    if registry.keys:
        clamped = max(0, min(state.active_index, len(registry.keys) - 1))
        if clamped != state.active_index:
            state.active_index = clamped
            changed = True
    else:
        if state.active_index != 0:
            state.active_index = 0
            changed = True

    if changed:
        save_state(config, state)
    return state


def save_state(config: Config, state: State) -> None:
    path = _state_path(config)
    payload = json.dumps(state.to_dict(), indent=2) + "\n"
    with file_lock(path):
        atomic_write_text(path, payload)


def mark_last_used(state: State, label: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if label not in state.keys:
        state.keys[label] = KeyState()
    state.keys[label].last_used = now


def record_request(state: State, label: str, status_code: int) -> None:
    if label not in state.keys:
        state.keys[label] = KeyState()
    key_state = state.keys[label]
    key_state.request_count += 1
    if status_code == 401:
        key_state.error_401 += 1
    elif status_code == 403:
        key_state.error_403 += 1
    elif status_code == 429:
        key_state.error_429 += 1
    elif 500 <= status_code <= 599:
        key_state.error_5xx += 1
