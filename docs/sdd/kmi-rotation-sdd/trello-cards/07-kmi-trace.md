# Card 07: KMI Manager CLI - Trace logs + TUI

| Field | Value |
|-------|-------|
| **ID** | KMI-07 |
| **Story Points** | 4 |
| **Depends On** | 06 |
| **Sprint** | 3 |

## User Story

> As an operator, I want `kmi --trace` to visualize request routing and show confidence >=95%.

## Context

Read before starting:
- [requirements.md#7-traceability--confidence](../requirements.md)
- [gaps.md#gap-003-trace-window-ui](../gaps.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git (session/wire logs patterns)

## Must Have

- [ ] JSONL trace log per request
- [ ] TUI tailing trace log
- [ ] Confidence metric displayed

## Instructions

### Step 1: Trace logging

```python
# File: src/kmi_manager_cli/trace.py
# - append JSONL: ts_msk, req_id, key_label, endpoint, status, latency_ms
```

### Step 2: TUI viewer

```python
# File: src/kmi_manager_cli/trace_tui.py
# - rich live table
# - summary panel with confidence %
```

### Step 3: Wire CLI flag

```python
# File: src/kmi_manager_cli/cli.py
# - --trace command launches TUI
```

### Step 4: Verification

```bash
kmi --trace
```

## Acceptance Criteria

- [ ] Trace log JSONL updated per request
- [ ] TUI displays rolling window with confidence
- [ ] Trace exits cleanly on Ctrl+C

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
