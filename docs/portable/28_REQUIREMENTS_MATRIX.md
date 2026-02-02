# Requirements & Compatibility Matrix

## Runtime
- Python: 3.9+
- OS: Linux/macOS/Windows (POSIX permissions checks are skipped on Windows)

## Python deps (high level)
- Typer (CLI)
- Rich (TUI)
- FastAPI + Uvicorn (proxy)
- httpx (upstream)
- python-dotenv (env files)

## External tools (optional)
- `lsof` — required for auto‑stop in `kmi proxy` and `kmi proxy-stop`.

## Compatibility notes
- If `lsof` is missing, proxy auto‑stop will fail with a clear message.
- If `KMI_DRY_RUN=1`, no upstream requests are made.
- If `KMI_PROXY_ALLOW_REMOTE=0`, proxy must bind to localhost.

