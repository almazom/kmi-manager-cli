# Safe Edits

- Prefer appending to `.env` and `~/.zshrc` rather than replacing.
- Never delete user key files without explicit request.
- If `KMI_PROXY_LISTEN` changes, update both `.env` and `KIMI_BASE_URL`.
- Use `kmi proxy` (auto‑kills old listener) rather than manual kill.
- Use `kmi doctor` after any change.

