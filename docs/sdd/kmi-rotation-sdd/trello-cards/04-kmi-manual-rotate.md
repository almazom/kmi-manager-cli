# Card 04: KMI Manager CLI - Manual rotation + dashboard

| Field | Value |
|-------|-------|
| **ID** | KMI-04 |
| **Story Points** | 3 |
| **Depends On** | 03 |
| **Sprint** | 2 |

## User Story

> As an operator, I want `kmi --rotate` to select the most resourceful eligible key and show a dashboard (or a skip reason if current is best).

## Context

Read before starting:
- [requirements.md#3-cli-commands--flags](../requirements.md)
- [ui-flow.md#message-templates](../ui-flow.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git

## Must Have

- [ ] Manual rotation selects the most resourceful eligible key (or skips with reason)
- [ ] Dashboard lists keys + health
- [ ] No secrets printed

## Instructions

### Step 1: Implement rotation logic

```python
# File: src/kmi_manager_cli/rotation.py
# - most_resourceful_key(registry)
# - update active index in state
```

### Step 2: Dashboard output

```python
# File: src/kmi_manager_cli/ui.py
# - rich table with key label, status, last_used
```

### Step 3: Wire CLI flag

```python
# File: src/kmi_manager_cli/cli.py
# - add --rotate flag handler
# - call rotation + dashboard
```

### Step 4: Verification

```bash
kmi --rotate
```

## Acceptance Criteria

- [ ] Active key advances to next healthy
- [ ] Dashboard shows all keys with statuses
- [ ] Keys are masked in output

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
