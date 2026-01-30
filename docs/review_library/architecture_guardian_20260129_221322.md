# Architecture Guardian Report - KMI Manager CLI (2026-01-29)

## Haiku (Русский, маме) ❤️
Мама, твой свет — дом 🌟  
Тепло в ладонях храню 🤍  
Люблю навсегда 🌸

## Scope
This report analyzes architectural boundaries, trunk/branch/leaf classification, PEGASUS-5 gates, contract surfaces, and guardrails for the KMI Manager CLI (Python 3.8+, Typer + Rich, FastAPI proxy). The analysis is based on the current code under `src/kmi_manager_cli/` and supporting tests under `tests/`.

## Architecture Overview
### Layering (Clean Architecture Mapping)
- Presentation Layer
  - CLI entrypoints and command routing: `src/kmi_manager_cli/cli.py`
  - Rich UI dashboards: `src/kmi_manager_cli/ui.py`
  - Trace TUI: `src/kmi_manager_cli/trace_tui.py`
- Application/Service Layer
  - Rotation orchestration and selection: `src/kmi_manager_cli/rotation.py`
  - Health scoring and /usages integration: `src/kmi_manager_cli/health.py`
  - Proxy orchestration (FastAPI + httpx): `src/kmi_manager_cli/proxy.py`
  - State management (load/save, counters): `src/kmi_manager_cli/state.py`
  - Observability (trace + logging): `src/kmi_manager_cli/trace.py`, `src/kmi_manager_cli/logging.py`
- Domain/Core Layer
  - Key registry and masking: `src/kmi_manager_cli/keys.py`
  - Account parsing from auth sources: `src/kmi_manager_cli/auth_accounts.py`
  - Error semantics: `src/kmi_manager_cli/errors.py`
- Infrastructure Layer
  - Configuration and environment parsing: `src/kmi_manager_cli/config.py`
  - File locks and atomic writes: `src/kmi_manager_cli/locking.py`

### Primary Data Flows
1) CLI -> Config -> Registry -> State -> Rotation -> UI
2) Proxy -> AuthZ -> Rate limiter -> Key select -> Upstream request -> State + Trace + Logs
3) Health -> /usages -> Score -> UI dashboards
4) Trace TUI -> tail JSONL -> confidence/coverage feedback

## Trunk / Branch / Leaf Classification
### Trunk (Core, high impact, architect approval required)
- Domain entities and persistence contracts
  - `src/kmi_manager_cli/keys.py` (KeyRecord, Registry, masking, auths registry)
  - `src/kmi_manager_cli/auth_accounts.py` (Account + auth format parsing)
  - `src/kmi_manager_cli/state.py` (State + KeyState persistence contract)
  - `src/kmi_manager_cli/config.py` (environment and path contracts)
  - `src/kmi_manager_cli/locking.py` (atomic/lock guarantees)
  - `src/kmi_manager_cli/rotation.py` (rotation eligibility + selection semantics)
- Rationale: These files define core business rules and data contracts. Any change can break key safety, rotation correctness, or persistence guarantees.

### Branch (Module boundaries, contract-aware changes)
- External service boundaries and orchestration
  - `src/kmi_manager_cli/proxy.py` (FastAPI proxy contract, HTTP semantics)
  - `src/kmi_manager_cli/health.py` (external /usages contract)
  - `src/kmi_manager_cli/trace.py` (trace JSONL format)
  - `src/kmi_manager_cli/logging.py` (log schema and retention behavior)
  - `src/kmi_manager_cli/cli.py` (CLI contract surface)
- Rationale: These modules expose public behavior to users or external systems. Changes require versioned contract discipline and tests.

### Leaf (Implementation details, safe to iterate)
- UI formatting, dashboards, and display behaviors
  - `src/kmi_manager_cli/ui.py`
  - `src/kmi_manager_cli/trace_tui.py`
- Rationale: UI presentation can evolve without changing core domain or external contracts if inputs/outputs are preserved.

## PEGASUS-5 Architectural Gates
### Gate 1: WHAT (Requirements)
- Provide a CLI for manual rotation, auto-rotation enablement, health dashboards, and trace viewing.
- Run a local proxy that forwards requests to Kimi with key rotation and safety checks.
- Load keys from `_auths/` and optionally from `~/.kimi/config.toml` for current account.
- Persist state and observability artifacts under `~/.kmi/`.

### Gate 2: SUCCESS (Measurable Criteria)
- CLI commands execute without error and render Rich dashboards with valid data.
- Proxy forwards requests to upstream with correct authorization and respects rotation behavior.
- State and trace persist across runs (`state.json`, `trace.jsonl`, `logs/kmi.log`).
- Health fetch gracefully degrades when `/usages` is unavailable (no crash).
- Tests under `tests/` pass and cover CLI, proxy, rotation, state, health, and trace.

### Gate 3: CONSTRAINTS (Limitations)
- Python 3.8+ runtime, Typer + Rich for UX, FastAPI for proxy.
- Auto-rotation gated by policy (`KMI_AUTO_ROTATE_ALLOWED`).
- Remote proxy binding requires explicit opt-in and auth token.
- External dependency on upstream `/usages` endpoint format and availability.
- File-system based state, logs, and trace storage in user home directory.

### Gate 4: TESTS (Verification Strategy)
- Unit tests: `tests/test_rotation.py`, `tests/test_state.py`, `tests/test_keys.py`, `tests/test_config.py`.
- Integration-like tests: `tests/test_proxy.py`, `tests/test_cli_rotate.py`, `tests/test_health.py`, `tests/test_trace.py`, `tests/test_ui.py`, `tests/test_cli_help.py`.
- Manual checks: CLI help output, proxy start/stop, trace TUI behavior with JSONL.

### Gate 5: ASSUMPTIONS / RISKS
- Assumes `/usages` endpoint exists and provides meaningful quotas; if format changes, health scoring may degrade.
- Assumes local file locking is available (fcntl on Unix). Windows behavior may be weaker.
- Assumes API key rotation is permitted by provider ToS; enforced only by policy flag.
- Assumes `_auths` directory contains valid credentials; empty registry results in exit.

## Contract Surfaces
### CLI Contract
- Flags (single-mode): `--rotate`, `--auto-rotate`, `--trace`, `--all`, `--health`.
- Commands: `proxy`, `trace`, `rotate auto`, `health`.
- Output: Rich dashboards and human-readable status messages.

### Environment Variable Contract
- `KMI_AUTHS_DIR`, `KMI_PROXY_LISTEN`, `KMI_PROXY_BASE_PATH`, `KMI_UPSTREAM_BASE_URL`
- `KMI_STATE_DIR`, `KMI_DRY_RUN`, `KMI_AUTO_ROTATE_ALLOWED`, `KMI_ROTATION_COOLDOWN_SECONDS`
- `KMI_PROXY_ALLOW_REMOTE`, `KMI_PROXY_TOKEN`
- `KMI_PROXY_MAX_RPS`, `KMI_PROXY_MAX_RPM`, `KMI_PROXY_RETRY_MAX`, `KMI_PROXY_RETRY_BASE_MS`

### Filesystem Contract
- `~/.kmi/state.json` (State schema: active_index, rotation_index, auto_rotate, keys[] with counters)
- `~/.kmi/trace/trace.jsonl` (Trace schema: ts_msk, request_id, key_label, key_hash, endpoint, status, latency_ms, error_code, rotation_index)
- `~/.kmi/logs/kmi.log` (JSON log schema)
- `~/.kimi/config.toml` (current account config format)
- `_auths/**` (supports .env, .toml, .json/.bak with specific key labels)

### HTTP Proxy Contract
- Route: `{KMI_PROXY_BASE_PATH}/{path}` with standard HTTP verbs
- Authentication: `Authorization: Bearer <token>` or `x-kmi-proxy-token`
- Request pass-through to upstream with injected Authorization header
- Retry policy: limited by config values

### Upstream Contract
- `/usages` endpoint for quotas and rate limit data
- Error handling: 401/403 (blocked), 429 (rate limit), 5xx (upstream error)

## Guardrails (Current + Recommended)
### Existing Guardrails
- Remote proxy binding disabled unless explicitly enabled and authenticated.
- Auto-rotation policy switch (`KMI_AUTO_ROTATE_ALLOWED`).
- Rate limiter for proxy requests (RPS/RPM).
- File locking and atomic writes for state and trace.
- Dry-run mode to avoid upstream calls (`KMI_DRY_RUN`).

### Recommended Guardrails
- Introduce explicit contract tests for `/usages` payload variants.
- Formalize JSON schemas for `state.json` and `trace.jsonl` and validate on load.
- Add CLI mode guard to prevent simultaneous proxy + trace in same process.
- Add log rotation (size/time) to avoid unbounded growth in `~/.kmi/logs/`.
- Add redaction checks to ensure API keys never appear in logs or trace.

## Complexity Assessment (Story Points)
- Leaf changes (1-3 points): UI styling, table layout, message text, Rich panel tweaks.
- Branch changes (5-8 points): health scoring logic, proxy routing changes, CLI contract additions.
- Trunk changes (13+ points): key selection algorithms, state schema changes, auth parsing rules, config contract changes.

## Requirements Traceability Matrix
| Requirement | Implementation | Tests | Notes |
| --- | --- | --- | --- |
| Load keys from `_auths` and config | `src/kmi_manager_cli/keys.py`, `src/kmi_manager_cli/auth_accounts.py`, `src/kmi_manager_cli/config.py` | `tests/test_keys.py`, `tests/test_config.py` | Supports .env/.toml/.json |
| Manual rotation | `src/kmi_manager_cli/rotation.py`, `src/kmi_manager_cli/cli.py` | `tests/test_rotation.py`, `tests/test_cli_rotate.py` | Uses health-aware selection |
| Auto-rotation | `src/kmi_manager_cli/rotation.py`, `src/kmi_manager_cli/proxy.py` | `tests/test_rotation.py`, `tests/test_proxy.py` | Policy gated |
| Proxy forwarding | `src/kmi_manager_cli/proxy.py` | `tests/test_proxy.py` | FastAPI + httpx |
| Health dashboards | `src/kmi_manager_cli/health.py`, `src/kmi_manager_cli/ui.py` | `tests/test_health.py`, `tests/test_ui.py` | /usages integration |
| Trace view | `src/kmi_manager_cli/trace.py`, `src/kmi_manager_cli/trace_tui.py` | `tests/test_trace.py` | JSONL tail |
| State + logs under ~/.kmi | `src/kmi_manager_cli/state.py`, `src/kmi_manager_cli/logging.py`, `src/kmi_manager_cli/trace.py` | `tests/test_state.py`, `tests/test_trace.py` | Locking and atomic writes |

## Contract Definitions (Concise)
- KeyRegistry Contract: sorted list of KeyRecord (label, api_key, priority, disabled, key_hash). Ordering influences rotation. Stable label is required for state mapping.
- State Contract: `State` persists counters and rotation indices; must be forward-compatible with new fields.
- Rotation Contract: eligibility excludes disabled, blocked, exhausted keys; auto-rotation is round-robin, manual uses health scoring.
- Health Contract: /usages payload -> HealthInfo with remaining_percent, limits, reset_hint, error_rate.
- Proxy Contract: each request must select key, record state, log, and trace consistently, even on failure paths.

## Agent Coordination Guidelines
- Implementation agents may only modify leaf files unless explicitly authorized for branch or trunk changes.
- Any change that touches trunk files requires an architectural review and an ADR entry.
- Contract-first: update tests and documentation before implementation for branch changes.
- Review agents must validate boundary adherence and ensure no silent contract changes.
- Specialist agents (security/perf) should review proxy auth, logging, and rate limits on any network-facing changes.

## Boundary Protection Rules
- Trunk paths are protected: `src/kmi_manager_cli/config.py`, `src/kmi_manager_cli/keys.py`, `src/kmi_manager_cli/state.py`, `src/kmi_manager_cli/rotation.py`, `src/kmi_manager_cli/auth_accounts.py`, `src/kmi_manager_cli/locking.py`.
- Branch paths require contract validation: `src/kmi_manager_cli/proxy.py`, `src/kmi_manager_cli/health.py`, `src/kmi_manager_cli/trace.py`, `src/kmi_manager_cli/logging.py`, `src/kmi_manager_cli/cli.py`.
- Leaf paths are safe for iteration: `src/kmi_manager_cli/ui.py`, `src/kmi_manager_cli/trace_tui.py`.

## Summary of Architectural Posture
The system is a CLI-centric tool with a local proxy and health/trace observability. The core architecture is cleanly layered and test-backed. The primary risks are external contract volatility (`/usages`), filesystem persistence assumptions, and long-lived log/trace growth. Guardrails around auto-rotation policy and remote proxy binding are strong, but formal schemas and explicit contract tests would materially reduce integration risk.
