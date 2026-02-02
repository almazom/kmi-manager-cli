# Upgrade and Migration

## Update code

```
cd <repo>
git pull
pip install -e .
```

## State migration

`state.json` is migrated automatically on load. If corrupted, it is renamed with `.corrupt.<timestamp>`.

## Trace/log rotation

Rotations are controlled by `KMI_TRACE_MAX_MB`, `KMI_TRACE_BACKUPS`, `KMI_LOG_MAX_MB`, `KMI_LOG_BACKUPS`.

