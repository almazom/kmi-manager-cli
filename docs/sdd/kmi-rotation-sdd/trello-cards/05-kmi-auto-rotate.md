# Card 05: KMI Manager CLI - Auto rotation engine

| Field | Value |
|-------|-------|
| **ID** | KMI-05 |
| **Story Points** | 4 |
| **Depends On** | 04 |
| **Sprint** | 2 |

## User Story

> As an operator, I want auto round-robin rotation per request so load is evenly distributed.

## Context

Read before starting:
- [requirements.md#4-key-storage--rotation-rules](../requirements.md)
- [requirements.md#7-traceability--confidence](../requirements.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git

## Must Have

- [ ] Round-robin per request in proxy (sequential, cyclic)
- [ ] Skip unhealthy keys
- [ ] Mark `exhausted` on 429/403 and skip until cooldown
- [ ] Optional toggle to disable auto rotation (SLA/ToS compliance)
- [ ] Persist rotation index

## Instructions

### Step 1: Add rotation policy

```python
# File: src/kmi_manager_cli/rotation.py
# - select_key_round_robin(registry, health)
# - update index per request
# - mark_exhausted(key, cooldown_seconds)
```

### Step 2: Integrate with proxy handler

```python
# File: src/kmi_manager_cli/proxy.py
# - on each request, call select_key_round_robin()
# - attach key to trace context
# - if key exhausted, skip to next
```

### Step 3: Enable CLI flag

```python
# File: src/kmi_manager_cli/cli.py
# - --auto_rotate toggles auto mode in state
```

### Step 4: Verification

```bash
kmi --auto_rotate
# Send 10 requests through proxy, check alternating keys in trace
```

## Acceptance Criteria

- [ ] Requests distribute across healthy keys in sequential order
- [ ] Unhealthy keys are skipped
- [ ] Exhausted keys re-enable after cooldown
- [ ] Auto-rotate can be disabled via config
- [ ] Rotation state persists across restarts

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
