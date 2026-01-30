# Card 02: KMI Manager CLI - Key registry + _auths loader

| Field | Value |
|-------|-------|
| **ID** | KMI-02 |
| **Story Points** | 3 |
| **Depends On** | 01 |
| **Sprint** | 1 |

## User Story

> As an operator, I want `_auths/` keys discovered automatically so I can rotate without editing config.

## Context

Read before starting:
- [requirements.md#4-key-storage--rotation-rules](../requirements.md)
- [gaps.md#gap-001-key-file-format-in-_auths_](../gaps.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git

## Must Have

- [ ] Load all `*.env` files from `_auths/`
- [ ] Mask keys in all outputs
- [ ] Persist registry state in `${KMI_STATE_DIR}/state.json`

## Instructions

### Step 1: Implement key registry model

```python
# File: src/kmi_manager_cli/keys.py
# - KeyRecord(label, api_key, priority, disabled)
# - Registry(list[KeyRecord], active_index)
```

### Step 2: Implement `_auths` loader

```python
# File: src/kmi_manager_cli/keys.py
# - load_env_file(path)
# - parse KMI_API_KEY, KMI_KEY_LABEL, KMI_KEY_PRIORITY, KMI_KEY_DISABLED
# - build registry (sorted by priority desc, label asc)
```

### Step 3: Persist state

```python
# File: src/kmi_manager_cli/state.py
# - read/write state.json in KMI_STATE_DIR
# - store active_index + last_used timestamps
```

### Step 4: Verification

```bash
# Example load
KMI_AUTHS_DIR=_auths python -m kmi_manager_cli.cli --all
```

## Acceptance Criteria

- [ ] Registry loads multiple keys from `_auths/`
- [ ] Active key index persists between runs
- [ ] Output masks API keys

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
