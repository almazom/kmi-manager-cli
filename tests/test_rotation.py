from __future__ import annotations

from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.health import HealthInfo
from kmi_manager_cli.rotation import (
    mark_blocked,
    mark_exhausted,
    next_healthy_index,
    rotate_manual,
    select_key_for_request,
    select_key_round_robin,
)
from kmi_manager_cli.state import KeyState, State


def test_next_healthy_skips_disabled() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a", disabled=True),
            KeyRecord(label="b", api_key="sk-b", disabled=False),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    idx = next_healthy_index(registry, state)
    assert idx == 1


def test_rotate_manual_updates_index() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    key, rotated, reason = rotate_manual(registry, state)
    assert key.label == "b"
    assert rotated is True
    assert reason is None
    assert state.active_index == 1


def test_round_robin_sequence() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
            KeyRecord(label="c", api_key="sk-c"),
        ]
    )
    state = State(rotation_index=0)
    assert select_key_round_robin(registry, state).label == "a"
    assert select_key_round_robin(registry, state).label == "b"
    assert select_key_round_robin(registry, state).label == "c"


def test_round_robin_skips_exhausted() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ]
    )
    state = State(rotation_index=0, keys={"a": KeyState(), "b": KeyState()})
    mark_exhausted(state, "a", cooldown_seconds=3600)
    key = select_key_round_robin(registry, state)
    assert key.label == "b"


def test_select_key_for_request_manual_fallback() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a", disabled=True),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    key = select_key_for_request(registry, state, auto_rotate=False)
    assert key.label == "b"


def test_select_key_for_request_allows_403() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0, keys={"a": KeyState(error_403=1)})
    key = select_key_for_request(registry, state, auto_rotate=False)
    assert key.label == "a"


def test_select_key_for_request_skips_blocked() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0, keys={"a": KeyState(), "b": KeyState()})
    mark_blocked(state, "a", reason="payment_required", block_seconds=3600)
    key = select_key_for_request(registry, state, auto_rotate=False)
    assert key.label == "b"


def test_select_key_for_request_requires_usage_ok() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="warn",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
            usage_ok=False,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=80.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
            usage_ok=True,
        ),
    }
    key = select_key_for_request(registry, state, auto_rotate=False, health=health, require_usage_ok=True)
    assert key.label == "b"


def test_select_key_fail_open_on_empty_cache() -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")], active_index=0)
    state = State(active_index=0)
    key = select_key_for_request(
        registry,
        state,
        auto_rotate=False,
        health=None,
        require_usage_ok=True,
        fail_open_on_empty_cache=True,
    )
    assert key is not None
    assert key.label == "a"


def test_rotate_manual_picks_most_resourceful() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
            remaining_percent=30.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=70.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health)
    assert key.label == "b"
    assert rotated is True
    assert reason is None
    assert state.active_index == 1


def test_rotate_manual_skips_when_current_best() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
            remaining_percent=80.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=50.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health)
    assert key.label == "a"
    assert rotated is False
    assert reason is not None
    assert state.active_index == 0


def test_rotate_manual_tie_breaks_when_prefer_next() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
            remaining_percent=100.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=100.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=True)
    assert key.label == "b"
    assert rotated is True
    assert reason is not None
    assert state.active_index == 1


def test_rotate_manual_prefers_lower_error_when_usage_missing() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="warn",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.2,
        ),
        "b": HealthInfo(
            status="warn",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.05,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health)
    assert key.label == "b"
    assert rotated is True
    assert reason is None
    assert state.active_index == 1


def test_rotate_manual_prefers_healthy_over_warn() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="warn",
            remaining_percent=90.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=10.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health)
    assert key.label == "b"
    assert rotated is True
    assert reason is None
    assert state.active_index == 1
