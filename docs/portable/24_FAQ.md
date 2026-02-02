# FAQ

Q: Why does `kmi e2e` show in trace but `kimi` does not?
A: `kimi` uses proxy only when `KIMI_BASE_URL` is set. Use `kmi kimi ...` or export env.

Q: How do I change the proxy port?
A: Update `KMI_PROXY_LISTEN` in `.env`, restart proxy, and update `KIMI_BASE_URL` in your shell.

Q: Where is trace stored?
A: `~/.kmi/trace/trace.jsonl`

Q: Does `kmi doctor` change anything?
A: By default, no. Use `--recheck-keys` or `--clear-blocklist` to update blocked keys.

Q: Why do I see permissions warnings?
A: Files are world/group readable. Fix with `chmod` (see security doc).
