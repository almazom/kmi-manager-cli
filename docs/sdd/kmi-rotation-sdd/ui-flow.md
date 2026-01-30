# KMI Manager CLI - UI Flow

> Status: DRAFT | Last updated: 2026-01-29 11:14:26 MSK

## User Journey

```
┌────────────────────────────────────────────┐
│            USER INPUT                      │
│  "kmi --rotate"                           │
└───────────────┬────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│          SYSTEM DETECTION                  │
│  Parse CLI flags/subcommands               │
└───────────────┬────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│        ACK + DASHBOARD                     │
│  Active key changed + health list          │
└───────────────┬────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│         RESULT DELIVERY                    │
│  Status + next steps                        │
└────────────────────────────────────────────┘
```

## Trace Flow

```
┌────────────────────────────────────────────┐
│  USER INPUT: "kmi --trace"                │
└───────────────┬────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│  TRACE WINDOW (TUI)                         │
│  - live request stream                      │
│  - per-key distribution                     │
│  - confidence >=95% indicator               │
└────────────────────────────────────────────┘
```

## Health Flow (All Keys)

```
┌────────────────────────────────────────────┐
│  USER INPUT: "kmi --all" / "kmi --health"  │
└───────────────┬────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│  HEALTH DASHBOARD                            │
│  - per-key status + quota                    │
│  - error rates + cooldowns                   │
└────────────────────────────────────────────┘
```

## Health Flow (Current Only)

```
┌────────────────────────────────────────────┐
│  USER INPUT: "kmi --current"               │
└───────────────┬────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│  CURRENT HEALTH PANEL                       │
│  - current account status                   │
│  - usage summary                            │
└────────────────────────────────────────────┘
```

## Status Flow

```
┌────────────────────────────────────────────┐
│  USER INPUT: "kmi --status" / "kmi status" │
└───────────────┬────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│  STATUS OUTPUT                               │
│  - active index + rotation index            │
│  - auto-rotate flag                          │
└────────────────────────────────────────────┘
```

## Message Templates

### Rotate Acknowledgment (switched)

```
✅ Rotation complete
Active key: {key_label}
Health: {status}

Top 5 keys:
- {key_1} {status_1}
- {key_2} {status_2}
...
```

### Rotate Acknowledgment (skipped)

```
⏭️ Rotation skipped
Reason: {reason}
Active key: {key_label}
```

### Auto-Rotate Enabled

```
✅ Auto-rotation enabled
Policy: round-robin
Healthy keys: {count}
Trace: kmi --trace
```

### Trace View Header

```
KMI TRACE  | window=200 | confidence=97% | healthy=5/6
------------------------------------------------------
{ts} {req_id} {key} {endpoint} {status} {latency}ms
```

## Open Questions

- none (auto-filled by up2u)
