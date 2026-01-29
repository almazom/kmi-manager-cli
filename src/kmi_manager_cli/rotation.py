from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import State, mark_last_used

if TYPE_CHECKING:
    from kmi_manager_cli.health import HealthInfo


def _is_eligible(key: KeyRecord, state: State, health: Optional[dict[str, HealthInfo]] = None) -> bool:
    if key.disabled:
        return False
    key_state = state.keys.get(key.label)
    if key_state and key_state.error_401 > 0:
        return False
    if is_exhausted(state, key.label):
        return False
    if health is None:
        return True
    info = health.get(key.label)
    status = info.status if info else None
    return status not in {"blocked", "exhausted"}


def next_healthy_index(registry: Registry, state: State, health: Optional[dict[str, HealthInfo]] = None) -> Optional[int]:
    if not registry.keys:
        return None
    total = len(registry.keys)
    start = state.active_index % total
    for offset in range(1, total + 1):
        idx = (start + offset) % total
        if _is_eligible(registry.keys[idx], state, health):
            return idx
    return None


def _resource_value(info: Optional[HealthInfo]) -> Optional[float]:
    if not info:
        return None
    if info.remaining_percent is not None:
        return float(info.remaining_percent)
    if info.remaining is not None and info.limit:
        if info.limit > 0:
            return (info.remaining / info.limit) * 100
    return None


def _status_rank(info: Optional[HealthInfo]) -> int:
    if info and info.status == "healthy":
        return 0
    if info and info.status == "warn":
        return 1
    return 2


def _manual_score(info: Optional[HealthInfo]) -> tuple:
    remaining = _resource_value(info)
    remaining_sort = -remaining if remaining is not None else 1.0
    error_rate = info.error_rate if info else 0.0
    return (_status_rank(info), remaining_sort, error_rate)


def _candidate_sort_key(key: KeyRecord, info: Optional[HealthInfo], is_current: bool) -> tuple:
    current_rank = 0 if is_current else 1
    return (*_manual_score(info), current_rank, key.label)


def _manual_candidates(
    registry: Registry, state: State, health: Optional[dict[str, HealthInfo]]
) -> list[tuple[int, KeyRecord, Optional[HealthInfo]]]:
    candidates: list[tuple[int, KeyRecord, Optional[HealthInfo]]] = []
    for idx, key in enumerate(registry.keys):
        if not _is_eligible(key, state, health):
            continue
        info = health.get(key.label) if health else None
        candidates.append((idx, key, info))
    return candidates


def most_resourceful_index(
    registry: Registry, state: State, health: Optional[dict[str, HealthInfo]] = None
) -> Optional[int]:
    if not registry.keys:
        return None
    if health is None:
        return next_healthy_index(registry, state, health)

    candidates = _manual_candidates(registry, state, health)
    if not candidates:
        return None

    current_idx = state.active_index
    best = min(
        candidates,
        key=lambda item: _candidate_sort_key(item[1], item[2], item[0] == current_idx),
    )
    return best[0]


def rotate_manual(
    registry: Registry, state: State, health: Optional[dict[str, HealthInfo]] = None
) -> tuple[KeyRecord, bool, Optional[str]]:
    current_idx = state.active_index
    idx = most_resourceful_index(registry, state, health)
    if idx is None:
        raise RuntimeError("No eligible keys to rotate")
    rotated = idx != current_idx
    if rotated:
        state.active_index = idx
        key = registry.keys[idx]
        mark_last_used(state, key.label)
        return key, True, None
    key = registry.keys[idx]
    reason = None
    if health is not None and registry.keys:
        candidates = _manual_candidates(registry, state, health)
        sorted_candidates = sorted(
            candidates,
            key=lambda item: _candidate_sort_key(item[1], item[2], False),
        )
        current_info = health.get(key.label)
        runner = next((entry for entry in sorted_candidates if entry[0] != current_idx), None)
        cur_remaining = _resource_value(current_info)
        if runner:
            runner_info = runner[2]
            runner_remaining = _resource_value(runner_info)
            current_score = _manual_score(current_info)
            runner_score = _manual_score(runner_info)
            if current_score == runner_score:
                if cur_remaining is not None:
                    reason = (
                        f"Current key ties for best remaining quota ({cur_remaining:.0f}%). "
                        f"Keeping current over {runner[1].label}."
                    )
                else:
                    reason = f"Current key ties for best score. Keeping current over {runner[1].label}."
            elif cur_remaining is not None and runner_remaining is not None:
                reason = (
                    f"Current key has higher remaining quota ({cur_remaining:.0f}%), "
                    f"next best {runner[1].label} has {runner_remaining:.0f}%."
                )
            elif current_info and runner_info and current_info.error_rate != runner_info.error_rate:
                reason = (
                    f"Current key has lower error rate ({current_info.error_rate * 100:.1f}%), "
                    f"next best {runner[1].label} has {runner_info.error_rate * 100:.1f}%."
                )
            elif current_info and runner_info and current_info.status != runner_info.status:
                reason = (
                    f"Current key has better status ({current_info.status}) than {runner[1].label} "
                    f"({runner_info.status})."
                )
        if reason is None and current_info:
            status = current_info.status
            reason = f"Current key already ranks best (status={status})."
    return key, False, reason


def select_key_round_robin(registry: Registry, state: State, health: Optional[dict[str, HealthInfo]] = None) -> Optional[KeyRecord]:
    if not registry.keys:
        return None
    total = len(registry.keys)
    start = state.rotation_index % total
    for offset in range(total):
        idx = (start + offset) % total
        candidate = registry.keys[idx]
        if _is_eligible(candidate, state, health):
            state.rotation_index = (idx + 1) % total
            mark_last_used(state, candidate.label)
            return candidate
    return None


def select_key_for_request(registry: Registry, state: State, auto_rotate: bool, health: Optional[dict[str, HealthInfo]] = None) -> Optional[KeyRecord]:
    if auto_rotate:
        return select_key_round_robin(registry, state, health)
    active = registry.active_key
    if active and _is_eligible(active, state, health):
        return active
    idx = next_healthy_index(registry, state, health)
    if idx is None:
        return None
    state.active_index = idx
    key = registry.keys[idx]
    mark_last_used(state, key.label)
    return key


def mark_exhausted(state: State, label: str, cooldown_seconds: int) -> None:
    until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
    if label not in state.keys:
        return
    state.keys[label].exhausted_until = until.strftime("%Y-%m-%dT%H:%M:%SZ")


def is_exhausted(state: State, label: str) -> bool:
    key_state = state.keys.get(label)
    if not key_state or not key_state.exhausted_until:
        return False
    try:
        until = datetime.fromisoformat(key_state.exhausted_until.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) < until
