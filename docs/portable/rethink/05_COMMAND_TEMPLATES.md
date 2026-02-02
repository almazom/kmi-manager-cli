# Command Templates

## Start proxy + trace

```
kmi proxy
kmi --trace
```

## Force proxy request

```
kmi kimi --final-message-only --print -c "test"
```

## Fix env mismatch quickly

```
export KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1"
export KIMI_API_KEY="proxy"
```

## Check trace for token

```
rg -n "<TOKEN>" ~/.kmi/trace/trace.jsonl
```

