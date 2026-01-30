# Card 08: KMI Manager CLI - Error handling + logging

| Field | Value |
|-------|-------|
| **ID** | KMI-08 |
| **Story Points** | 3 |
| **Depends On** | 07 |
| **Sprint** | 3 |

## User Story

> As an operator, I want clear errors and structured logs so failures are diagnosable.

## Context

Read before starting:
- [requirements.md#9-logging](../requirements.md)
- [requirements.md#10-error-handling](../requirements.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git

## Must Have

- [ ] JSON structured logs with MSK timestamps
- [ ] HTTP 503 when all keys blocked
- [ ] Actionable error messages in CLI
- [ ] ToS/SLA warning when auto-rotation enabled

## Instructions

### Step 1: Logging utilities

```python
# File: src/kmi_manager_cli/logging.py
# - JSON logger
# - write to ${KMI_STATE_DIR}/logs/kmi.log
```

### Step 2: Error mapping

```python
# File: src/kmi_manager_cli/errors.py
# - map upstream errors to user-friendly messages
# - 401/403 => blocked key
# - 429/5xx => warn
# - 429/403 => exhausted (cooldown)
```

### Step 3: Proxy error responses

```python
# File: src/kmi_manager_cli/proxy.py
# - if no healthy keys: return 503 + remediation
```

### Step 4: Verification

```bash
# Force empty _auths to verify error path
kmi --all
```

## Acceptance Criteria

- [ ] Structured logs written in JSON
- [ ] CLI error messages include next steps
- [ ] 503 returned when all keys blocked
- [ ] Auto-rotation displays ToS/SLA reminder

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
