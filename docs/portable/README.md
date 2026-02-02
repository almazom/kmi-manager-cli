# Portable Runbook (AI Agent Friendly)

Goal: a repeatable, no-sudo setup for KMI Manager CLI + Kimi CLI that routes all `kimi` requests through the local proxy, with trace/log visibility.

This document is designed for an AI agent to execute automatically. Any step requiring sudo is explicitly called out.

---

## Assumptions

- Working directory is the repo root.
- Shell is zsh (adjust if different).
- No sudo is used unless explicitly stated.

---

## 0) Quick facts (paths + commands)

- Project .env: `./.env`
- Auth keys dir: `_auths/` or `KMI_AUTHS_DIR`
- State/log/trace dir: `~/.kmi/`
- Kimi CLI config: `~/.kimi/config.toml`
- Proxy base path default: `/kmi-rotor/v1`

Key commands:
- Start proxy: `kmi proxy`
- Start proxy (foreground): `kmi proxy --foreground`
- Stop proxy: `kmi proxy-stop --yes`
- Restart proxy: `kmi proxy-restart --yes`
- Proxy logs: `kmi proxy-logs --no-follow --lines 200`
- Auto-rotate: `kmi rotate auto`
- Trace TUI: `kmi --trace`
- Doctor: `kmi doctor`
- Status JSON: `kmi status --json`
- Kimi wrapper (forces proxy env): `kmi kimi --final-message-only --print -c "test"`

---

## 1) Install (no sudo)

From repo root:

```
pip install -e .
```

Verify:

```
kmi --help
```

---

## 2) Configure .env (no sudo)

Create or edit `./.env`:

```
KMI_DRY_RUN=0
KMI_WRITE_CONFIG=1
KMI_ROTATE_ON_TIE=1
KMI_AUTO_ROTATE_ALLOWED=1
KMI_AUTHS_DIR=~/.kimi/_auths
KMI_STATE_DIR=~/.kmi
KMI_PROXY_LISTEN=127.0.0.1:54244
KMI_PROXY_BASE_PATH=/kmi-rotor/v1
KMI_PROXY_REQUIRE_TLS=1
KMI_PROXY_TLS_TERMINATED=0
KMI_TIMEZONE=Europe/Moscow
KMI_LOCALE=en
```

Notes:
- Change `KMI_PROXY_LISTEN` if the port is busy.
- If you want Moscow time in logs/trace, keep `KMI_TIMEZONE=Europe/Moscow`.

---

## 3) Auth keys (no sudo)

Place key files in `KMI_AUTHS_DIR` (default `~/.kimi/_auths`). Example:

```
mkdir -p ~/.kimi/_auths
cat > ~/.kimi/_auths/alpha.env <<'EOK'
KMI_API_KEY=sk-your-key
KMI_KEY_LABEL=alpha
EOK
```

---

## 4) Shell env for Kimi CLI (no sudo)

Make sure `kimi` always uses the proxy.

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

---

## 5) Start proxy (no sudo)

```
kmi proxy
```

Behavior:
- It auto-detects any existing listener on the configured port, stops it, then starts a fresh proxy.
- If `lsof` is missing, it will warn and exit (manual stop required).
- Runs in background by default and logs to `~/.kmi/logs/proxy.out`.
- Use `kmi proxy --foreground` to keep it attached to the terminal.

---

## 6) Enable auto-rotation (no sudo)

```
kmi rotate auto
```

---

## 7) Trace view (no sudo)

```
kmi --trace
```

---

## 8) Send a test request (no sudo)

Use either:

```
# Normal kimi (uses proxy via env + alias)
kimi --final-message-only --print -c "test"

# Forced proxy wrapper (ignores shell env)
kmi kimi --final-message-only --print -c "test"
```

You should see `/chat/completions` lines in `kmi --trace`.

---

## 9) Doctor report (no sudo)

```
kmi doctor
```

If permissions are insecure, you may see a warning. Fix (no sudo needed):

```
chmod 700 ~/.kimi/_auths
chmod 600 ~/.kimi/_auths/*
chmod 700 ~/.kmi ~/.kmi/trace ~/.kmi/logs
chmod 600 ~/.kmi/state.json ~/.kmi/trace/trace.jsonl ~/.kmi/logs/kmi.log
```

---

## 10) Troubleshooting (no sudo)

### Port already in use

```
kmi proxy-restart --yes
```

### Kimi requests not in trace

```
echo $KIMI_BASE_URL
# Must match the proxy URL

kmi doctor
```

If still failing, run:

```
KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1" KIMI_API_KEY="proxy" \
  kimi --final-message-only --print -c "test"
```

---

## 11) Steps that require sudo (ask user)

These cannot be done by the AI agent automatically without user approval.

### Set system timezone to Moscow

```
sudo timedatectl set-timezone Europe/Moscow
```

Verify:

```
timedatectl
```

---

## 12) Optional: verify proxy is listening (no sudo)

```
lsof -nP -iTCP:54244 -sTCP:LISTEN
```

---

## 13) Minimal checklist (agent-friendly)

- [ ] `pip install -e .`
- [ ] `.env` configured (KMI_PROXY_LISTEN, KMI_TIMEZONE)
- [ ] `~/.zshrc` exports KIMI_BASE_URL + KIMI_API_KEY
- [ ] `source ~/.zshrc`
- [ ] `kmi proxy`
- [ ] optional: `kmi status --json`
- [ ] `kmi rotate auto`
- [ ] `kmi --trace`
- [ ] `kimi ...` or `kmi kimi ...`
- [ ] `kmi doctor` clean
