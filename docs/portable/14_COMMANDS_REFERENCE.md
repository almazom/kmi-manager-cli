# Commands Reference

CLI: `kmi`

Main modes:
- `kmi --rotate` — manual rotate
- `kmi --auto_rotate` / `kmi --auto-rotate` — enable auto‑rotation
- `kmi --trace` — trace TUI
- `kmi --all` / `kmi --health` — health for all keys
- `kmi --current` — health for current key
- `kmi --status` — status summary

Subcommands:
- `kmi rotate` — manual rotate (same as `--rotate`)
- `kmi rotate auto` — enable auto‑rotation
- `kmi rotate off` — disable auto‑rotation
- `kmi proxy` — start proxy in background (auto‑stops existing listener)
- `kmi proxy --foreground` — start proxy in foreground
- `kmi proxy-stop` — stop proxy on configured port
- `kmi proxy-restart` — stop + start proxy
- `kmi proxy-logs` — tail proxy daemon logs
- `kmi proxy-logs --app --since 10m` — filter app logs by time
- `kmi trace` — trace TUI
- `kmi health` — health for all keys
- `kmi status` — status summary
- `kmi status --json` — status summary (JSON)
- `kmi e2e` — run round‑robin proxy test
- `kmi doctor` — diagnostics
- `kmi kimi ...` — run kimi CLI with proxy env injected

Examples:

```
# start proxy
kmi proxy

# enable auto-rotation
kmi rotate auto

# trace view
kmi --trace

# run a forced proxy kimi request
kmi kimi --final-message-only --print -c "test"
```
