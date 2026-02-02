# Proxy API

Base URL:
- `http://127.0.0.1:<PORT>/kmi-rotor/v1`

The proxy forwards requests to upstream with the selected API key.

## Auth for remote access

If `KMI_PROXY_ALLOW_REMOTE=1` and proxy is bound to a non‑local interface:
- You must set `KMI_PROXY_TOKEN`
- Requests must include either:
  - `Authorization: Bearer <token>`
  - `x-kmi-proxy-token: <token>`

## TLS requirements

When bound to non‑local interface:
- `KMI_PROXY_REQUIRE_TLS=1` requires TLS termination
- Set `KMI_PROXY_TLS_TERMINATED=1` when TLS is handled upstream

## Rate limits

- `KMI_PROXY_MAX_RPS`, `KMI_PROXY_MAX_RPM` (global)
- `KMI_PROXY_MAX_RPS_PER_KEY`, `KMI_PROXY_MAX_RPM_PER_KEY` (per key)

## Retries

- `KMI_PROXY_RETRY_MAX` and `KMI_PROXY_RETRY_BASE_MS`

