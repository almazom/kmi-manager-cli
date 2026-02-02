from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kmi_manager_cli.health import HealthInfo
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.rotation import (
    clear_blocked,
    is_blocked,
    is_exhausted,
    mark_blocked,
    mark_exhausted,
    most_resourceful_index,
    next_healthy_index,
    rotate_manual,
    select_key_round_robin,
    select_key_for_request,
)
from kmi_manager_cli.state import KeyState, State


def test_mark_blocked_sets_reason_and_blocks() -> None:
    state = State(keys={"a": KeyState()})
    mark_blocked(state, "a", reason="payment_required", block_seconds=0)
    assert is_blocked(state, "a") is True
    assert state.keys["a"].blocked_reason == "payment_required"
    assert state.keys["a"].blocked_until is None


def test_is_blocked_expires() -> None:
    state = State(keys={"a": KeyState()})
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    state.keys["a"].blocked_until = past.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert is_blocked(state, "a") is False


def test_is_blocked_invalid_timestamp() -> None:
    state = State(keys={"a": KeyState(blocked_until="not-a-time")})
    assert is_blocked(state, "a") is True


def test_clear_blocked_counts() -> None:
    state = State(
        keys={
            "a": KeyState(blocked_reason="x"),
            "b": KeyState(blocked_reason="y"),
        }
    )
    assert clear_blocked(state) == 2
    assert clear_blocked(state) == 0


def test_mark_exhausted_requires_existing_key() -> None:
    state = State(keys={})
    mark_exhausted(state, "missing", cooldown_seconds=60)
    assert is_exhausted(state, "missing") is False


def test_next_healthy_skips_error_401() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")]
    )
    state = State(active_index=0, keys={"a": KeyState(error_401=1)})
    idx = next_healthy_index(registry, state)
    assert idx == 1


def test_select_key_round_robin_prefers_healthy() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")]
    )
    state = State(rotation_index=0, keys={"a": KeyState(), "b": KeyState()})
    health = {
        "a": HealthInfo(
            status="warn",
            remaining_percent=10.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=90.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key = select_key_round_robin(registry, state, health=health)
    assert key.label == "b"


def test_select_key_round_robin_falls_back_to_warn() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")]
    )
    state = State(rotation_index=0, keys={"a": KeyState(), "b": KeyState()})
    health = {
        "a": HealthInfo(
            status="warn",
            remaining_percent=10.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="warn",
            remaining_percent=20.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key = select_key_round_robin(registry, state, health=health)
    assert key.label == "a"


def test_rotate_manual_tie_prefer_next() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
            remaining_percent=50.0,
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
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=True)
    assert rotated is True
    assert key.label == "b"
    assert reason is not None


def test_rotate_manual_tie_keeps_current() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
            remaining_percent=50.0,
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
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=False)
    assert rotated is False
    assert key.label == "a"
    assert reason is not None


def test_rotate_manual_reason_higher_remaining() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
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
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=False)
    assert rotated is False
    assert key.label == "a"
    assert "higher remaining quota" in reason


def test_rotate_manual_reason_lower_error_rate() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
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
            error_rate=0.01,
        ),
        "b": HealthInfo(
            status="warn",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.2,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=False)
    assert rotated is False
    assert key.label == "a"
    assert "lower error rate" in reason


def test_rotate_manual_reason_better_status() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="warn",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=False)
    assert rotated is False
    assert key.label == "a"
    assert "better status" in reason


def test_select_key_requires_usage_ok_fail_closed() -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")], active_index=0)
    state = State(active_index=0)
    key = select_key_round_robin(
        registry,
        state,
        health=None,
        require_usage_ok=True,
        fail_open_on_empty_cache=False,
    )
    assert key is None


def test_next_healthy_index_empty_registry() -> None:
    registry = Registry(keys=[], active_index=0)
    state = State(active_index=0)
    assert next_healthy_index(registry, state) is None


def test_next_healthy_index_no_eligible() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a", disabled=True)],
        active_index=0,
    )
    state = State(active_index=0)
    assert next_healthy_index(registry, state) is None


def test_most_resourceful_index_with_health(tmp_path) -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="warn",
            remaining_percent=10.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=20.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    assert most_resourceful_index(registry, state, health=health) == 1


def test_most_resourceful_index_empty_registry() -> None:
    registry = Registry(keys=[], active_index=0)
    state = State(active_index=0)
    assert most_resourceful_index(registry, state, health={}) is None


def test_rotate_manual_no_rotation_when_current_best() -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")], active_index=0)
    state = State(active_index=0)
    key, rotated, reason = rotate_manual(registry, state)
    assert key.label == "a"
    assert rotated is False
    assert reason is None


def test_rotate_manual_raises_when_no_keys() -> None:
    registry = Registry(keys=[], active_index=0)
    state = State(active_index=0)
    try:
        rotate_manual(registry, state)
    except RuntimeError as exc:
        assert "No eligible keys" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_rotate_manual_reason_tie_without_remaining() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
        "b": HealthInfo(
            status="healthy",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=False)
    assert rotated is False
    assert "ties for best score" in reason


def test_rotate_manual_reason_already_best_status() -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
        active_index=0,
    )
    state = State(active_index=0)
    health = {
        "a": HealthInfo(
            status="healthy",
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
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
        ),
    }
    key, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=False)
    assert rotated is False
    assert "already ranks best" in reason


def test_select_key_round_robin_empty_registry() -> None:
    registry = Registry(keys=[], active_index=0)
    state = State(rotation_index=0)
    assert select_key_round_robin(registry, state) is None


def test_select_key_requires_usage_ok_missing_health_entry() -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")], active_index=0)
    state = State(active_index=0)
    health = {
        "other": HealthInfo(
            status="healthy",
            remaining_percent=100.0,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=0.0,
            usage_ok=True,
        )
    }
    key = select_key_round_robin(
        registry,
        state,
        health=health,
        require_usage_ok=True,
        fail_open_on_empty_cache=False,
    )
    assert key is None


def test_select_key_for_request_auto_rotate(tmp_path) -> None:
    registry = Registry(
        keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")],
        active_index=0,
    )
    state = State(rotation_index=0)
    key = select_key_for_request(registry, state, auto_rotate=True)
    assert key is not None


def test_select_key_for_request_none_when_no_eligible() -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a", disabled=True)], active_index=0)
    state = State(active_index=0)
    key = select_key_for_request(registry, state, auto_rotate=False)
    assert key is None


def test_mark_blocked_creates_key_state() -> None:
    state = State(keys={})
    mark_blocked(state, "new", reason="payment", block_seconds=10)
    assert "new" in state.keys


def test_clear_blocked_with_missing_label() -> None:
    state = State(keys={})
    assert clear_blocked(state, "missing") == 0


def test_clear_blocked_with_unblocked_label() -> None:
    state = State(keys={"a": KeyState()})
    assert clear_blocked(state, "a") == 0


def test_is_exhausted_invalid_timestamp() -> None:
    state = State(keys={"a": KeyState(exhausted_until="bad")})
    assert is_exhausted(state, "a") is False
