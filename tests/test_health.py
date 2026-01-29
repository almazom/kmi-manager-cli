from __future__ import annotations

from pathlib import Path

from kmi_manager_cli.config import Config
from kmi_manager_cli.health import Usage, get_health_map, score_key
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import KeyState, State


def test_score_key_blocked_on_auth_error() -> None:
    state = KeyState(error_401=1)
    usage = Usage(remaining_percent=50.0, used=None, limit=None, remaining=None, reset_hint=None, limits=[], raw={})
    assert score_key(usage, state, exhausted=False) == "blocked"


def test_score_key_warn_on_low_quota() -> None:
    state = KeyState(request_count=10)
    usage = Usage(remaining_percent=10.0, used=None, limit=None, remaining=None, reset_hint=None, limits=[], raw={})
    assert score_key(usage, state, exhausted=False) == "warn"


def test_score_key_warn_on_forbidden() -> None:
    state = KeyState(error_403=1, request_count=1)
    usage = Usage(remaining_percent=50.0, used=None, limit=None, remaining=None, reset_hint=None, limits=[], raw={})
    assert score_key(usage, state, exhausted=False) == "warn"


def test_score_key_warn_on_usage_missing() -> None:
    state = KeyState()
    assert score_key(None, state, exhausted=False) == "warn"


def test_score_key_exhausted() -> None:
    state = KeyState()
    usage = Usage(remaining_percent=100.0, used=None, limit=None, remaining=None, reset_hint=None, limits=[], raw={})
    assert score_key(usage, state, exhausted=True) == "exhausted"


def test_get_health_map_dry_run(tmp_path: Path) -> None:
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
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-a")])
    state = State()
    health = get_health_map(config, registry, state)
    assert health["alpha"].status == "healthy"
