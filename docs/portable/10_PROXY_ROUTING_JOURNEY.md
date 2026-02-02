# Proxy Routing Journey (Detailed, AI‑Agent Friendly)

This is the **long-form, detailed** account of how we ensured **all Kimi CLI requests go through the proxy** and appear in `kmi --trace`.

Use this as a strict checklist for an AI agent.

---

## Problem Statement

- `kmi e2e` requests were visible in `kmi --trace`.
- Regular `kimi` CLI requests **did not appear in trace** (skipped proxy).

This means: **proxy works**, but **kimi CLI is bypassing it**.

---

## Root Cause (Primary)

`kimi` CLI **does not read project `.env`** automatically.
It only uses **environment variables in the current shell**:

- `KIMI_BASE_URL`
- `KIMI_API_KEY`

If those are missing (or set to a different port), `kimi` goes directly to upstream, skipping proxy.

---

## Fix Strategy (Guaranteed)

### A) Inject env per command (always works)

```
KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1" \
KIMI_API_KEY="proxy" \
kimi --final-message-only --print -c "test"
```

### B) Persistent shell env + alias (recommended)

Add to `~/.zshrc`:

```
export KMI_ENV_PATH="$HOME/TOOLS/kimi_manager_cli/.env"
export KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1"
export KIMI_API_KEY="proxy"
export TZ=Europe/Moscow
export KMI_TIMEZONE=Europe/Moscow
alias kimi='KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1" KIMI_API_KEY="proxy" command kimi'
```

Apply:

```
source ~/.zshrc
```

### C) Use wrapper (safest for AI)

We added:

```
kmi kimi --final-message-only --print -c "test"
```

This **forces proxy env** every time, independent of shell state.

---

## Verification Steps (Strict)

### 1) Proxy listens

```
kmi proxy
```
Expected output includes:

```
Starting proxy at http://127.0.0.1:54244/kmi-rotor/v1
Proxy started in background (daemon).
```

If port is in use, `kmi proxy` auto‑stops the existing listener and restarts it.
Use `kmi proxy --foreground` to keep it attached to the terminal.

### 2) Trace TUI open

```
kmi --trace
```

### 3) Send request through proxy

```
kmi kimi --final-message-only --print -c "test"
```

### 4) Confirm in trace

Look for a line with `/chat/completions` and your prompt hint.

---

## Diagnostics Loop (AI Automation)

Send 3 requests and verify trace contains them:

```
for i in 1 2 3; do
  token="proxy-check-$i-$(date +%s)"
  kmi kimi --final-message-only --print -c "$token" >/dev/null
  sleep 1
  rg -n "$token" ~/.kmi/trace/trace.jsonl && echo "OK: $token" || echo "MISS: $token"
done
```

Expected: all tokens appear in trace.

---

## Common Failure Modes + Fix

### 1) Proxy port mismatch

Symptoms:
- `kmi proxy` listening on one port
- `KIMI_BASE_URL` points to a different port

Fix:
- Align `KMI_PROXY_LISTEN` in `.env`
- Update `KIMI_BASE_URL` in `~/.zshrc`

### 2) Env not applied in current shell

Symptoms:
- `echo $KIMI_BASE_URL` is empty

Fix:
```
source ~/.zshrc
```

### 3) Different terminal or IDE shell

Symptoms:
- Works in one terminal, fails in another

Fix:
- Apply same env in that terminal
- Or use `kmi kimi` wrapper (works everywhere)

---

## Proof of Fix (What we confirmed)

We ran a full confirmation loop:

- Proxy listening on `127.0.0.1:54244`
- `KIMI_BASE_URL` set to proxy URL
- `kimi` requests produced `/chat/completions` in trace

---

## Minimal AI Agent Script (No sudo)

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &

for i in 1 2 3; do
  kmi kimi --final-message-only --print -c "test-$i" >/dev/null
  sleep 1
done

kmi doctor
```

---

## If You Need Moscow Time

For shell/trace:

```
export TZ=Europe/Moscow
export KMI_TIMEZONE=Europe/Moscow
```

For system time (requires sudo):

```
sudo timedatectl set-timezone Europe/Moscow
```

---

## Summary

- `kmi e2e` uses proxy by design.
- `kimi` uses proxy **only** if `KIMI_BASE_URL` + `KIMI_API_KEY` are set.
- The safest route is `kmi kimi` wrapper.
- `kmi doctor` verifies current state.
