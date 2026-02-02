# Setup (No sudo)

This is a full setup that avoids sudo.

## 1) Install

```
pip install -e .
```

Verify:

```
kmi --help
```

## 2) Configure .env

Create or edit `./.env` in the repo root:

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

## 3) Add auth keys

```
mkdir -p ~/.kimi/_auths
cat > ~/.kimi/_auths/alpha.env <<'EOK'
KMI_API_KEY=sk-your-key
KMI_KEY_LABEL=alpha
EOK
```

## 4) Start proxy

```
kmi proxy
```
Note: runs in background by default. Use `kmi proxy --foreground` if you want it attached to the terminal.

## 5) Enable auto-rotation

```
kmi rotate auto
```

## 6) Trace view

```
kmi --trace
```

## 7) Send a test request

```
kmi kimi --final-message-only --print -c "test"
```

You should see `/chat/completions` in trace.

## 8) Doctor report

```
kmi doctor
```
