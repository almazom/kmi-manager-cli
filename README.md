# KMI Manager CLI

Spec-driven implementation for KMI Manager CLI. See `docs/sdd/kmi-rotation-sdd/` for requirements.

## Requirements

- Python 3.9+

## Quickstart

1. Create an auth file under `_auths/`:

```bash
mkdir -p _auths
cat > _auths/alpha.env << 'EOF'
KMI_API_KEY=sk-your-key
KMI_KEY_LABEL=alpha
EOF
```

2. Copy `.env.example` to `.env` (optional) and adjust values:

```bash
cp .env.example .env
```

3. Install and run:

```bash
pip install -e .
kmi --help
kmi --all
kmi proxy
```

Notes:
- `KMI_DRY_RUN=1` means upstream requests are simulated. Set to `0` for live traffic.
- Remote proxy binding requires `KMI_PROXY_ALLOW_REMOTE=1` and `KMI_PROXY_TOKEN`.

## Paths

- State and logs: `~/.kmi/` (state.json, logs, trace.jsonl)
- Current Kimi CLI account: `~/.kimi/config.toml`
- Auth keys: `_auths/` (or `KMI_AUTHS_DIR`)
