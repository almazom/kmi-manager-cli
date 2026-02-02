# Config Reference (KMI_*)

All values are read from `.env` or environment variables.

Core:
- `KMI_AUTHS_DIR` (default `_auths`) — auth key folder
- `KMI_STATE_DIR` (default `~/.kmi`) — state/log/trace dir
- `KMI_DRY_RUN` (default `1`) — simulate upstream requests
- `KMI_AUTO_ROTATE_ALLOWED` (default `0`) — allow auto‑rotation
- `KMI_AUTO_ROTATE_E2E` (default `1`) — run e2e on auto‑rotate enable
- `KMI_ROTATION_COOLDOWN_SECONDS` (default `300`) — cooldown for exhausted keys
- `KMI_WRITE_CONFIG` (default `1`) — write selected key into `~/.kimi/config.toml`
- `KMI_ROTATE_ON_TIE` (default `1`) — manual rotate advances on tie

Proxy:
- `KMI_PROXY_LISTEN` (default `127.0.0.1:54123`)
- `KMI_PROXY_BASE_PATH` (default `/kmi-rotor/v1`)
- `KMI_PROXY_ALLOW_REMOTE` (default `0`)
- `KMI_PROXY_TOKEN` (default empty)
- `KMI_PROXY_REQUIRE_TLS` (default `1`)
- `KMI_PROXY_TLS_TERMINATED` (default `0`)
- `KMI_PROXY_MAX_RPS` / `KMI_PROXY_MAX_RPM`
- `KMI_PROXY_MAX_RPS_PER_KEY` / `KMI_PROXY_MAX_RPM_PER_KEY`
- `KMI_PROXY_RETRY_MAX` (default `0`)
- `KMI_PROXY_RETRY_BASE_MS` (default `250`)

Upstream:
- `KMI_UPSTREAM_BASE_URL` (default `https://api.kimi.com/coding/v1`)
- `KMI_UPSTREAM_ALLOWLIST` (comma-separated hosts)

Trace/log:
- `KMI_TRACE_MAX_MB` (default `5`)
- `KMI_TRACE_BACKUPS` (default `3`)
- `KMI_LOG_MAX_MB` (default `5`)
- `KMI_LOG_BACKUPS` (default `3`)

Output:
- `KMI_TIMEZONE` (default `local`)
- `KMI_LOCALE` (default `en`)
- `KMI_PLAIN` (default `0`)
- `KMI_NO_COLOR` (default `0`)

Security:
- `KMI_ENFORCE_FILE_PERMS` (default `1`)
- `KMI_AUDIT_ACTOR` (optional tag)

Kimi CLI (not read by kmi, but by `kimi`):
- `KIMI_BASE_URL`
- `KIMI_API_KEY`

