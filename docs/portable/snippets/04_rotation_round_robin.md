# Round‑Robin Rotation

Source: `src/kmi_manager_cli/rotation.py`

```python
def select_key_round_robin(registry: Registry, state: State, health: Optional[dict[str, HealthInfo]] = None) -> Optional[KeyRecord]:
    if not registry.keys:
        return None
    total = len(registry.keys)
    start = state.rotation_index % total
    if health:
        for offset in range(total):
            idx = (start + offset) % total
            candidate = registry.keys[idx]
            info = health.get(candidate.label)
            if info and info.status == "healthy" and _is_eligible(candidate, state, health):
                state.rotation_index = (idx + 1) % total
                mark_last_used(state, candidate.label)
                return candidate
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
```
