# Failure Recovery Runbook

## Proxy fails to start

1) `kmi proxy-restart --yes`
2) Verify port:
   `lsof -nP -iTCP:54244 -sTCP:LISTEN`

## Trace not updating

1) `kmi doctor`
2) Force proxy call:
   `kmi kimi --final-message-only --print -c "test"`
3) Check trace file:
   `tail -n 5 ~/.kmi/trace/trace.jsonl`

## Health shows errors

- Check `/usages` in logs:
  `rg -n "usage_fetch_failed" ~/.kmi/logs/kmi.log`

## Key stuck blocked/exhausted

- Inspect `~/.kmi/state.json`
- Optionally clear state (reset counters):
  `rm -f ~/.kmi/state.json`

