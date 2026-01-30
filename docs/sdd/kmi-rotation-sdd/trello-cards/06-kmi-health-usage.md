# Card 06: KMI Manager CLI - Health + usage scoring

| Field | Value |
|-------|-------|
| **ID** | KMI-06 |
| **Story Points** | 3 |
| **Depends On** | 05 |
| **Sprint** | 2 |

## User Story

> As an operator, I want per-key health based on quota and errors so rotation avoids bad keys.

## Context

Read before starting:
- [requirements.md#6-health--usage](../requirements.md)
- [gaps.md#gap-005-health-scoring-thresholds](../gaps.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git (usage endpoint)

## Must Have

- [ ] Fetch `/usages` per key
- [ ] Health scoring (healthy/warn/blocked)
- [ ] Error counters from proxy logs
- [ ] Exhausted status with cooldown timer

## Instructions

### Step 1: Usage fetcher

```python
# File: src/kmi_manager_cli/health.py
# - fetch_usage(base_url, api_key)
# - parse remaining quota
```

### Step 2: Health scoring

```python
# File: src/kmi_manager_cli/health.py
# - score_key(usage, error_stats)
# - thresholds from requirements
# - cooldown tracking for exhausted keys
```

### Step 3: CLI health view

```python
# File: src/kmi_manager_cli/cli.py
# - --all / health command shows health table
```

### Step 4: Verification

```bash
kmi --all
```

## Acceptance Criteria

- [ ] Health state computed for each key
- [ ] Blocked keys are flagged on 401/403
- [ ] Usage fetch failures degrade to warn
- [ ] Exhausted keys re-enable after cooldown

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
