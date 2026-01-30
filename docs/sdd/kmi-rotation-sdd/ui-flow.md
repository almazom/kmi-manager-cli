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
