# Kimi CLI auth findings (local + upstream)

Timestamp (MSK): 2026-01-29 11:00:30 MSK
Scope: local ~/.kimi inspection + upstream Kimi CLI docs/source

## 1) Local ~/.kimi inventory (secrets redacted)
Observed files and folders:
- /home/almaz/.kimi/config.toml
- /home/almaz/.kimi/config.json.bak
- /home/almaz/.kimi/device_id
- /home/almaz/.kimi/kimi.json
- /home/almaz/.kimi/mcp.json
- /home/almaz/.kimi/logs/
- /home/almaz/.kimi/sessions/
- /home/almaz/.kimi/user-history/

Auth-related signals locally:
- config.toml contains provider api_key entries
- device_id is generated and used by OAuth device flow
- no credentials directory exists on this machine (suggests keyring or no OAuth login yet)

## 2) Upstream documented locations (summary)
- Default config file: ~/.kimi/config.toml
- Kimi CLI creates config.toml on first run
- Env vars can override api_key and base_url
- /login opens browser to authorize; /logout clears stored credentials

## 3) Source-level (code) notes
- Share dir is ~/.kimi (created if missing)
- OAuth tokens are saved to system keyring when available
- If keyring not available, tokens are saved under ~/.kimi/credentials/<name>.json
- For managed providers, API key can be derived from OAuth access token

## 4) Health/usage signal (code)
- Kimi CLI has a usage fetcher that calls a base_url + /usages endpoint using Authorization: Bearer <key>
- This can be used to score key health and remaining quota for rotation

## 5) Implication for kmi wrapper
- Primary auth file to rotate: ~/.kimi/config.toml
- Preferred approach: avoid editing config.toml; inject KIMI_API_KEY via env per request or via proxy
- Proxy-based rotation avoids modifying Kimi CLI internals and keeps keys externalized

