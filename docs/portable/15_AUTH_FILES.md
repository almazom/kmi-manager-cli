# Auth Files

Supported formats in `KMI_AUTHS_DIR`:
- `.env`
- `.toml`
- `.json`
- `.json.bak`

Each file should contain a Kimi API key.

## .env example

```
KMI_API_KEY=sk-your-key
KMI_KEY_LABEL=alpha
KMI_UPSTREAM_BASE_URL=https://api.kimi.com/coding/v1
KMI_KEY_PRIORITY=0
KMI_KEY_DISABLED=0
```

## .toml example

Standard Kimi CLI config is supported (providers section). Keep it consistent with your Kimi CLI layout.

## .json example

JSON provider format with `providers` key (see existing Kimi CLI config).

Notes:
- Duplicate API keys are deduped.
- Priority and disabled are read from `.env` files only.
- Labels are derived from file name or `KMI_KEY_LABEL`.

