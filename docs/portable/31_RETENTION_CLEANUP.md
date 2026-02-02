# Retention & Cleanup

## Trace rotation

Controlled by:
- `KMI_TRACE_MAX_MB`
- `KMI_TRACE_BACKUPS`

## Log rotation

Controlled by:
- `KMI_LOG_MAX_MB`
- `KMI_LOG_BACKUPS`

## Manual cleanup

```
rm -f ~/.kmi/trace/trace.jsonl*
rm -f ~/.kmi/logs/kmi.log*
```

## State reset (careful)

```
rm -f ~/.kmi/state.json
```

This resets rotation index and error counters.

