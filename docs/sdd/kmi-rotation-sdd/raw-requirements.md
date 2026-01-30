# Raw Requirements (verbatim + cleaned)

Timestamp (MSK): 2026-01-29 11:14:26 MSK

## Verbatim (user-supplied, lightly cleaned)
- Need to understand how Kimi CLI auth works by inspecting repo and ~/.kimi
- Create KMI Manager CLI wrapper (global `kmi --help`)
- Manual rotation: `kmi --rotate` selects the most resourceful eligible key (or skips with reason)
- Auto round-robin rotation: `kmi --auto_rotate`
- Traceability window: `kmi --trace` to visualize each request and prove round-robin (95%+ confidence)
- Use `_auths/` directory to store multiple keys for rotation
- Dashboard should show all keys and their health state
- Need usage/quota info per account to assess key health
- Proxy approach: each request uses a different key (round robin) through proxy when enabled
- Proxy API must be unique (not default/banal)
- Keep secrets out of code; use `.env`

## Cleaned summary
- Build a global CLI wrapper `kmi` that manages multiple Kimi API keys with manual and automatic rotation.
- Implement a local proxy that selects keys per request (round robin), with a unique base path.
- Provide a trace view to show request routing and distribution confidence >= 95%.
- Provide a dashboard to show key health based on usage/quota and error signals.
- Store secrets in `.env` and `_auths/` only; do not hardcode.
