from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import KeyState, State, mark_last_used

if TYPE_CHECKING:
    from kmi_manager_cli.health import HealthInfo


def _is_eligible(key: KeyRecord, state: State, health: Optional[dict[str, HealthInfo]] = None) -> bool:
    if key.disabled:
        return False
    if is_blocked(state, key.label):
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


def _usage_ok(
    health: Optional[dict[str, HealthInfo]],
    label: str,
    require_usage_ok: bool,
    fail_open_on_empty_cache: bool,
) -> bool:
    if not require_usage_ok:
        return True
    if not health:
        return fail_open_on_empty_cache
    info = health.get(label)
    if info is None:
        return fail_open_on_empty_cache
    return bool(info.usage_ok)


def next_healthy_index(
    registry: Registry,
    state: State,
    health: Optional[dict[str, HealthInfo]] = None,
    require_usage_ok: bool = False,
    fail_open_on_empty_cache: bool = False,
) -> Optional[int]:
    if not registry.keys:
        return None
    total = len(registry.keys)
    start = state.active_index % total
    for offset in range(1, total + 1):
        idx = (start + offset) % total
        if _is_eligible(registry.keys[idx], state, health) and _usage_ok(
            health, registry.keys[idx].label, require_usage_ok, fail_open_on_empty_cache
        ):
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
    registry: Registry,
    state: State,
    health: Optional[dict[str, HealthInfo]] = None,
    require_usage_ok: bool = False,
    fail_open_on_empty_cache: bool = False,
) -> Optional[int]:
    if not registry.keys:
        return None
    if health is None:
        return next_healthy_index(
            registry,
            state,
            health,
            require_usage_ok=require_usage_ok,
            fail_open_on_empty_cache=fail_open_on_empty_cache,
        )

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
    registry: Registry,
    state: State,
    health: Optional[dict[str, HealthInfo]] = None,
    prefer_next_on_tie: bool = False,
) -> tuple[KeyRecord, bool, Optional[str]]:
    candidates = _manual_candidates(registry, state, health) if health is not None else None
    current_idx = state.active_index
    if health is None:
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
        return key, False, None

    if not candidates:
        raise RuntimeError("No eligible keys to rotate")

    scored = [(idx, _manual_score(info), key, info) for idx, key, info in candidates]
    best_score = min(score for _, score, _, _ in scored)
    best_indices = [idx for idx, score, _, _ in scored if score == best_score]

    if current_idx in best_indices:
        if prefer_next_on_tie and len(best_indices) > 1:
            ordered_best = [idx for idx, _, _, _ in scored if idx in best_indices]
            pos = ordered_best.index(current_idx)
            idx = ordered_best[(pos + 1) % len(ordered_best)]
            state.active_index = idx
            key = registry.keys[idx]
            mark_last_used(state, key.label)
            return key, True, "Tie for best score; rotating to next eligible."
        idx = current_idx
        key = registry.keys[idx]
        reason = None
        if registry.keys:
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

    idx = next(idx for idx, score, _, _ in scored if score == best_score)
    state.active_index = idx
    key = registry.keys[idx]
    mark_last_used(state, key.label)
    return key, True, None


def select_key_round_robin(
    registry: Registry,
    state: State,
    health: Optional[dict[str, HealthInfo]] = None,
    require_usage_ok: bool = False,
    fail_open_on_empty_cache: bool = False,
) -> Optional[KeyRecord]:
    if not registry.keys:
        return None
    total = len(registry.keys)
    start = state.rotation_index % total
    if health:
        for offset in range(total):
            idx = (start + offset) % total
            candidate = registry.keys[idx]
            info = health.get(candidate.label)
            if (
                info
                and info.status == "healthy"
                and _is_eligible(candidate, state, health)
                and _usage_ok(health, candidate.label, require_usage_ok, fail_open_on_empty_cache)
            ):
                state.rotation_index = (idx + 1) % total
                mark_last_used(state, candidate.label)
                return candidate
    for offset in range(total):
        idx = (start + offset) % total
        candidate = registry.keys[idx]
        if _is_eligible(candidate, state, health) and _usage_ok(
            health, candidate.label, require_usage_ok, fail_open_on_empty_cache
        ):
            state.rotation_index = (idx + 1) % total
            mark_last_used(state, candidate.label)
            return candidate
    return None


def select_key_for_request(
    registry: Registry,
    state: State,
    auto_rotate: bool,
    health: Optional[dict[str, HealthInfo]] = None,
    require_usage_ok: bool = False,
    fail_open_on_empty_cache: bool = False,
) -> Optional[KeyRecord]:
    if auto_rotate:
        return select_key_round_robin(
            registry,
            state,
            health,
            require_usage_ok=require_usage_ok,
            fail_open_on_empty_cache=fail_open_on_empty_cache,
        )
    active = registry.active_key
    if active and _is_eligible(active, state, health) and _usage_ok(
        health, active.label, require_usage_ok, fail_open_on_empty_cache
    ):
        return active
    idx = next_healthy_index(
        registry,
        state,
        health,
        require_usage_ok=require_usage_ok,
        fail_open_on_empty_cache=fail_open_on_empty_cache,
    )
    if idx is None:
        return None
    state.active_index = idx
    key = registry.keys[idx]
    mark_last_used(state, key.label)
    return key


def mark_blocked(state: State, label: str, reason: str, block_seconds: Optional[int]) -> None:
    if label not in state.keys:
        state.keys[label] = KeyState()
    key_state = state.keys[label]
    key_state.blocked_reason = reason
    if block_seconds is None or block_seconds <= 0:
        key_state.blocked_until = None
        return
    until = datetime.now(timezone.utc) + timedelta(seconds=block_seconds)
    key_state.blocked_until = until.strftime("%Y-%m-%dT%H:%M:%SZ")


def clear_blocked(state: State, label: Optional[str] = None) -> int:
    if label is not None:
        key_state = state.keys.get(label)
        if not key_state:
            return 0
        if key_state.blocked_reason is None and key_state.blocked_until is None:
            return 0
        key_state.blocked_reason = None
        key_state.blocked_until = None
        return 1
    cleared = 0
    for key_state in state.keys.values():
        if key_state.blocked_reason is None and key_state.blocked_until is None:
            continue
        key_state.blocked_reason = None
        key_state.blocked_until = None
        cleared += 1
    return cleared


def is_blocked(state: State, label: str) -> bool:
    key_state = state.keys.get(label)
    if not key_state:
        return False
    if key_state.blocked_reason is None and key_state.blocked_until is None:
        return False
    if key_state.blocked_until:
        try:
            until = datetime.fromisoformat(key_state.blocked_until.replace("Z", "+00:00"))
        except ValueError:
            return True
        return datetime.now(timezone.utc) < until
    return True


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
