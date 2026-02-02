# Automation Scripts (Idempotent)

These are safe, repeatable scripts for AI agents.

## 1) Start fresh proxy + verify

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi doctor
```

Notes:
- `kmi proxy` runs in background by default (logs: `~/.kmi/logs/proxy.out`).
- Use `kmi proxy --foreground` if you want it attached to the terminal.

## 2) Verify trace pipeline

```
for i in 1 2 3; do
  token="proxy-check-$i-$(date +%s)"
  kmi kimi --final-message-only --print -c "$token" >/dev/null
  sleep 1
  rg -n "$token" ~/.kmi/trace/trace.jsonl && echo "OK: $token" || echo "MISS: $token"
done
```

## 2b) Loop until confidence >= 95%

Use built‑in E2E loop (stops early when confidence threshold is reached):

```
kmi e2e --min-confidence 95 --requests 200 --window 50 --batch 10
```

If you want to force retries until it succeeds:

```
until kmi e2e --min-confidence 95 --requests 200 --window 50 --batch 10; do
  sleep 2
done
```

## 3) One‑liner forced proxy request

```
KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1" KIMI_API_KEY="proxy" \
  kimi --final-message-only --print -c "test"
```

## 4) Machine-readable status (for scripts)

```
kmi status --json | jq -r '.proxy.running, .keys, .last_health_refresh'
```
