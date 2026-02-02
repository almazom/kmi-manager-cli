# Port & Env Conflicts

## Common conflicts

1) Proxy port busy
- Symptom: address already in use
- Fix: `kmi proxy` auto‑stops existing listener

2) KIMI_BASE_URL mismatch
- Symptom: `kimi` bypasses proxy
- Fix: align `.env` port and `~/.zshrc` env

3) Multiple shells
- Symptom: works in one terminal but not another
- Fix: `source ~/.zshrc` or use `kmi kimi` wrapper

## Verification commands

```
rg -n "KMI_PROXY_LISTEN" .env

echo $KIMI_BASE_URL

echo $KIMI_API_KEY

kmi doctor
```

