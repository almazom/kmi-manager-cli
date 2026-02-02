# Portable Setup for Any New Computer

Use this on a fresh machine. It assumes **no sudo** unless explicitly called out.

---

## 0) Variables (edit these once)

Set these values for your machine:

- `REPO_DIR` (where the repo lives)
- `PROXY_PORT` (pick a free port, e.g., 54244)
- `TIMEZONE` (e.g., Europe/Moscow)

Example values:

```
REPO_DIR=$HOME/TOOLS/kimi_manager_cli
PROXY_PORT=54244
TIMEZONE=Europe/Moscow
```

---

## 1) Clone repo (no sudo)

```
mkdir -p "$REPO_DIR"
# clone your repo here (git clone ...)
```

---

## 2) Install (no sudo)

From repo root:

```
cd "$REPO_DIR"
pip install -e .
```

Verify:

```
kmi --help
```

---

## 3) Create/edit .env (no sudo)

Create `./.env` with:

```
KMI_DRY_RUN=0
KMI_WRITE_CONFIG=1
KMI_ROTATE_ON_TIE=1
KMI_AUTO_ROTATE_ALLOWED=1
KMI_AUTHS_DIR=~/.kimi/_auths
KMI_STATE_DIR=~/.kmi
KMI_PROXY_LISTEN=127.0.0.1:${PROXY_PORT}
KMI_PROXY_BASE_PATH=/kmi-rotor/v1
KMI_PROXY_REQUIRE_TLS=1
KMI_PROXY_TLS_TERMINATED=0
KMI_TIMEZONE=${TIMEZONE}
KMI_LOCALE=en
```

---

## 4) Add auth keys (no sudo)

```
mkdir -p ~/.kimi/_auths
cat > ~/.kimi/_auths/alpha.env <<'EOK'
KMI_API_KEY=sk-your-key
KMI_KEY_LABEL=alpha
EOK
```

---

## 5) Shell env (zsh) (no sudo)

Add to `~/.zshrc`:

```
export KMI_ENV_PATH="$REPO_DIR/.env"
export KIMI_BASE_URL="http://127.0.0.1:${PROXY_PORT}/kmi-rotor/v1"
export KIMI_API_KEY="proxy"
export TZ=${TIMEZONE}
export KMI_TIMEZONE=${TIMEZONE}
alias kimi='KIMI_BASE_URL="http://127.0.0.1:${PROXY_PORT}/kmi-rotor/v1" KIMI_API_KEY="proxy" command kimi'
```

Apply:

```
source ~/.zshrc
```

---

## 6) Start proxy (no sudo)

```
kmi proxy
```

This auto‑kills any old listener on the same port.

---

## 7) Enable auto‑rotation (no sudo)

```
kmi rotate auto
```

---

## 8) Trace + test (no sudo)

```
kmi --trace
```

In another terminal:

```
kmi kimi --final-message-only --print -c "test"
```

Expected: `/chat/completions` appears in trace.

---

## 9) Doctor (no sudo)

```
kmi doctor
```

---

## 10) Permissions (no sudo)

If doctor warns:

```
chmod 700 ~/.kimi/_auths
chmod 600 ~/.kimi/_auths/*
chmod 700 ~/.kmi ~/.kmi/trace ~/.kmi/logs
chmod 600 ~/.kmi/state.json ~/.kmi/trace/trace.jsonl ~/.kmi/logs/kmi.log
```

---

## 11) Sudo-only steps (ask user)

System timezone (optional):

```
sudo timedatectl set-timezone ${TIMEZONE}
```

Install `lsof` (for auto‑stop):

```
sudo apt-get install lsof
# or
sudo yum install lsof
# or
brew install lsof
```

