from __future__ import annotations

from pathlib import Path

from kmi_manager_cli.config import Config
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import load_state, save_state


def test_state_persists_active_index(tmp_path: Path) -> None:
    config = Config(
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
    )
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test-a")], active_index=0)

    state = load_state(config, registry)
    state.active_index = 0
    save_state(config, state)

    loaded = load_state(config, registry)
    assert loaded.active_index == 0
    assert "alpha" in loaded.keys
    assert loaded.schema_version == 1


def test_load_state_recovers_corrupt_file(tmp_path: Path) -> None:
    config = Config(
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
    )
    bad_state = tmp_path / "state.json"
    bad_state.write_text("{bad json")
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test-a")], active_index=0)

    state = load_state(config, registry)
    assert "alpha" in state.keys
    assert state.schema_version == 1
    corrupt_files = list(tmp_path.glob("state.json.corrupt.*"))
    assert corrupt_files
