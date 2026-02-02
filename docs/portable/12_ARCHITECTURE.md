# Architecture Overview

Components:

- CLI (Typer): `src/kmi_manager_cli/cli.py`
  - Commands: rotate, proxy, trace, doctor, status, health, e2e
- Proxy (FastAPI): `src/kmi_manager_cli/proxy.py`
  - Routes requests to upstream Kimi API
  - Selects key per request (round robin when auto‑rotate on)
- Rotation policy: `src/kmi_manager_cli/rotation.py`
  - Manual rotation (best key) and auto‑rotation (round robin)
- Health: `src/kmi_manager_cli/health.py`
  - Fetches `/usages` from upstream to estimate remaining quota
- Trace: `src/kmi_manager_cli/trace.py` + `trace_tui.py`
  - JSONL per request + live TUI view
- State: `src/kmi_manager_cli/state.py`
  - Persistent `state.json` with rotation index, errors, last used
- Logging: `src/kmi_manager_cli/logging.py`
  - JSON logs in `~/.kmi/logs/kmi.log`

Data flow (request):

1) Client (`kimi` or any HTTP client) -> local proxy
2) Proxy selects key -> forwards upstream
3) Proxy records state + trace + log
4) Trace TUI reads trace file

