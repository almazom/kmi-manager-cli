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
- `kmi proxy` runs in background by default; use `kmi proxy --foreground` to keep it in the terminal.
- `kmi doctor` shows a diagnostics report (proxy, env, auths, trace/log health).
- `kmi proxy-logs --no-follow --lines 200` tails proxy daemon logs (`--app` for app logs).
- `kmi proxy-logs --app --since 10m` filters app logs by time.
- `KMI_DRY_RUN=1` means upstream requests are simulated. Set to `0` for live traffic.
- Manual `--rotate` copies the selected `_auths/*.toml` into `~/.kimi/config.toml` when `KMI_WRITE_CONFIG=1` and dry-run is off.
- `KMI_ROTATE_ON_TIE=1` makes manual rotate advance even when all keys are tied for best.
- `.env` is loaded from the project root (override with `KMI_ENV_PATH`).
- `KMI_UPSTREAM_ALLOWLIST` can restrict upstream hosts (comma-separated, supports `*.domain`).
- Auto-rotation is opt-in; set `KMI_AUTO_ROTATE_ALLOWED=1` before enabling.
- Auto-rotation runs E2E by default; set `KMI_AUTO_ROTATE_E2E=0` to skip.
- By default, auto-rotation only uses "healthy" keys; set `KMI_ROTATE_INCLUDE_WARN=1` to also rotate keys with "warn" status (403 errors, low quota).
- Remote proxy binding requires `KMI_PROXY_ALLOW_REMOTE=1` and `KMI_PROXY_TOKEN`.
- For non-local proxy binding, run behind TLS and set `KMI_PROXY_TLS_TERMINATED=1` (or set `KMI_PROXY_REQUIRE_TLS=0` to override).
- Optional per-key limits: `KMI_PROXY_MAX_RPS_PER_KEY` and `KMI_PROXY_MAX_RPM_PER_KEY`.
- Payment-required responses block keys for `KMI_PAYMENT_BLOCK_SECONDS` (set to 0 for manual unblock).
- Strict pre-check: `KMI_REQUIRE_USAGE_BEFORE_REQUEST=1` blocks keys without a successful cached `/usages` check (refreshed in background every `KMI_USAGE_CACHE_SECONDS`). Use `KMI_FAIL_OPEN_ON_EMPTY_CACHE=1` to allow requests while the cache warms.
- Blocklist auto recheck: `KMI_BLOCKLIST_RECHECK_SECONDS` interval with `KMI_BLOCKLIST_RECHECK_MAX` keys per pass.
- `KMI_TIMEZONE` controls timestamps (default `local`; accepts `UTC`, `+03:00`, or IANA names).
- `KMI_LOCALE` controls human-facing summaries (default `en`, set `ru` for Russian).
- `--plain` / `--no-color` (or `KMI_PLAIN=1` / `KMI_NO_COLOR=1`) disable rich formatting.
- `KMI_AUDIT_ACTOR` tags audit events (auto-rotate enable/disable, config writes).

## Security and limitations

- Remote proxy access must be explicitly enabled and protected with token + TLS.
- State/log/trace files are plaintext; ensure filesystem permissions are tight.
- Enable auto-rotation only when compliant with provider ToS.
  - `KMI_ENFORCE_FILE_PERMS=1` (default) hardens permissions to 700/600 on POSIX systems.

## Paths

- State and logs: `~/.kmi/` (state.json, logs, trace.jsonl)
- Current Kimi CLI account: `~/.kimi/config.toml`
- Auth keys: `_auths/` (or `KMI_AUTHS_DIR`) supporting `.env`, `.toml`, `.json`, `.json.bak`
