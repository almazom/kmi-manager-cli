# Security & Permissions

Notes:
- Auth files and logs are plaintext.
- Keep permissions tight on shared machines.

Recommended permissions:

```
chmod 700 ~/.kimi/_auths
chmod 600 ~/.kimi/_auths/*
chmod 700 ~/.kmi ~/.kmi/trace ~/.kmi/logs
chmod 600 ~/.kmi/state.json ~/.kmi/trace/trace.jsonl ~/.kmi/logs/kmi.log
```

If you need to enable auto-rotation, ensure provider ToS allows it.

