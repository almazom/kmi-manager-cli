from __future__ import annotations

import json
from pathlib import Path

from kmi_manager_cli.config import Config
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import (
    KeyState,
    State,
    _migrate_state,
    load_state,
    mark_last_used,
    record_request,
)


def _make_config(tmp_path: Path) -> Config:
    return Config(
        auths_dir=tmp_path,
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com",
        state_dir=tmp_path,
        dry_run=True,
        auto_rotate_allowed=True,
        rotation_cooldown_seconds=300,
        proxy_allow_remote=False,
        proxy_token="",
        proxy_max_rps=0,
        proxy_max_rpm=0,
        proxy_retry_max=0,
        proxy_retry_base_ms=250,
        env_path=None,
        enforce_file_perms=False,
    )


def test_migrate_state_versions() -> None:
    data, changed = _migrate_state({"schema_version": 0})
    assert changed is True
    assert data["schema_version"] == 1

    data, changed = _migrate_state({"schema_version": 99})
    assert changed is True
    assert data["schema_version"] == 1


def test_migrate_state_invalid_schema_value() -> None:
    data, changed = _migrate_state({"schema_version": "bad"})
    assert changed is True
    assert data["schema_version"] == 1


def test_record_request_decrements_errors_on_success() -> None:
    state = State(keys={"a": KeyState(error_403=2, error_429=1, error_5xx=1)})
    record_request(state, "a", 200)
    assert state.keys["a"].error_403 == 1
    assert state.keys["a"].error_429 == 0
    assert state.keys["a"].error_5xx == 0


def test_record_request_tracks_401_and_403() -> None:
    state = State(keys={"a": KeyState()})
    record_request(state, "a", 401)
    record_request(state, "a", 403)
    assert state.keys["a"].error_401 == 1
    assert state.keys["a"].error_403 == 1


def test_mark_last_used_sets_timestamp() -> None:
    state = State()
    mark_last_used(state, "alpha")
    assert state.keys["alpha"].last_used is not None


def test_load_state_clamps_active_index(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")]
    )
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({"schema_version": 1, "active_index": 99, "keys": {}}) + "\n",
        encoding="utf-8",
    )

    state = load_state(config, registry)

    assert state.active_index == 1


def test_load_state_resets_active_index_when_registry_empty(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[])
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({"schema_version": 1, "active_index": 5, "keys": {}}) + "\n",
        encoding="utf-8",
    )

    state = load_state(config, registry)

    assert state.active_index == 0


def test_load_state_handles_schema_mismatch(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({"schema_version": 1, "active_index": 0, "keys": {}}) + "\n",
        encoding="utf-8",
    )

    def fake_from_dict(_data):
        return State(schema_version=99)

    monkeypatch.setattr("kmi_manager_cli.state.State.from_dict", fake_from_dict)
    state = load_state(config, registry)
    assert state.schema_version == 1
