# KMI Manager CLI

Spec-driven implementation for KMI Manager CLI. Canonical docs live under `docs/` (legacy `Docs/` may exist).
See `docs/sdd/kmi-rotation-sdd/` for requirements.

## Requirements

- Python 3.9+

## Quickstart

1. Create an auth file under `_auths/` (supports `.env`, `.toml`, `.json`, or `.json.bak`):

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
- Manual `--rotate` copies the selected `_auths/*.toml` into `~/.kimi/config.toml` when `KMI_WRITE_CONFIG=1` and dry-run is off.
- `KMI_ROTATE_ON_TIE=1` makes manual rotate advance even when all keys are tied for best.
- `.env` is loaded from the project root (override with `KMI_ENV_PATH`).
- `KMI_UPSTREAM_ALLOWLIST` can restrict upstream hosts (comma-separated, supports `*.domain`).
- Auto-rotation is opt-in; set `KMI_AUTO_ROTATE_ALLOWED=1` before enabling.
- Auto-rotation runs E2E by default; set `KMI_AUTO_ROTATE_E2E=0` to skip.
- Remote proxy binding requires `KMI_PROXY_ALLOW_REMOTE=1` and `KMI_PROXY_TOKEN`.
- For non-local proxy binding, run behind TLS and set `KMI_PROXY_TLS_TERMINATED=1` (or set `KMI_PROXY_REQUIRE_TLS=0` to override).
- Optional per-key limits: `KMI_PROXY_MAX_RPS_PER_KEY` and `KMI_PROXY_MAX_RPM_PER_KEY`.
- `KMI_TIMEZONE` controls timestamps (default `local`; accepts `UTC`, `+03:00`, or IANA names).
- `KMI_LOCALE` controls human-facing summaries (default `en`, set `ru` for Russian).
- `--plain` / `--no-color` (or `KMI_PLAIN=1` / `KMI_NO_COLOR=1`) disable rich formatting.
- `KMI_AUDIT_ACTOR` tags audit events (auto-rotate enable/disable, config writes).

## Paths

- State and logs: `~/.kmi/` (state.json, logs, trace.jsonl)
- Current Kimi CLI account: `~/.kimi/config.toml`
- Auth keys: `_auths/` (or `KMI_AUTHS_DIR`) supporting `.env`, `.toml`, `.json`, `.json.bak`
