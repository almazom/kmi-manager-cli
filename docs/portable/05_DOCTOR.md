# kmi doctor

Run diagnostics:

```
kmi doctor
```

Recheck blocked keys (live /usages calls, even in dry-run):

```
kmi doctor --recheck-keys
```

Clear blocked keys without checks:

```
kmi doctor --clear-blocklist
```

What it checks (examples):
- .env present
- auth keys available
- dry run on/off
- auto‑rotate policy allowed
- proxy listening
- Kimi env matches proxy
- state/trace/log presence
- permissions warnings

Exit codes:
- `0` if no FAIL
- `1` if any FAIL

If permissions are flagged:

```
chmod 700 ~/.kimi/_auths
chmod 600 ~/.kimi/_auths/*
chmod 700 ~/.kmi ~/.kmi/trace ~/.kmi/logs
chmod 600 ~/.kmi/state.json ~/.kmi/trace/trace.jsonl ~/.kmi/logs/kmi.log
```
