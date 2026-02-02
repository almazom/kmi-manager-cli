# Trace and Logs

## Trace TUI

```
kmi --trace
```

Trace file:
- `~/.kmi/trace/trace.jsonl`

## Log file

- `~/.kmi/logs/kmi.log`

## Send a test request

```
kmi kimi --final-message-only --print -c "test"
```

## Loop test (manual)

```
while true; do
  kmi kimi --final-message-only --print -c "ping $(date +%s)" >/dev/null
  sleep 2
done
```

## Tail trace/log

```
tail -f ~/.kmi/trace/trace.jsonl
```

```
tail -f ~/.kmi/logs/kmi.log
```

