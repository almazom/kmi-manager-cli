# AGENTS.md - AI Agent Guide for KMI Manager CLI

This document provides essential context for AI agents working on the KMI Manager CLI codebase.

## Project Overview

**KMI Manager CLI** is a production-grade Python CLI tool for managing API key rotation and proxying requests to the Kimi API. It solves the problem of handling multiple API keys with different quota limits, automatically rotating to the healthiest key.

### Core Capabilities

1. **Key Rotation**: Manual (resource-based) and automatic (round-robin) rotation
2. **Proxy Server**: FastAPI-based async proxy that sits between clients and upstream API
3. **Health Monitoring**: Tracks quota usage, error rates, and key status
4. **Request Tracing**: JSONL-based tracing for debugging rotation decisions
5. **State Management**: Persistent state with schema versioning and migrations

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│ KMI Proxy   │────▶│  Upstream   │
│  (kimi-cli) │     │  (FastAPI)  │     │   (Kimi)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐       ┌──────────┐      ┌──────────┐
   │  State  │       │  Health  │      │  Trace   │
   │  (JSON) │       │  (Cache) │      │  (JSONL) │
   └─────────┘       └──────────┘      └──────────┘
```

## Module Reference

### Core Modules

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `cli.py` | Typer CLI entry points | `app`, `proxy()`, `main_callback()` |
| `config.py` | Configuration loading | `Config` (dataclass), `load_config()` |
| `proxy.py` | FastAPI proxy server | `create_app()`, `ProxyContext`, `RateLimiter` |
| `rotation.py` | Key selection algorithms | `rotate_manual()`, `select_key_round_robin()` |
| `health.py` | Health/usage fetching | `fetch_usage()`, `get_health_map()`, `HealthInfo` |
| `state.py` | State persistence | `State`, `KeyState`, `load_state()`, `save_state()` |
| `keys.py` | Key registry | `KeyRecord`, `Registry`, `load_auths_dir()` |
| `auth_accounts.py` | Auth file parsing | `Account`, `load_accounts_from_auths_dir()` |

### Supporting Modules

| Module | Purpose |
|--------|---------|
| `ui.py` | Rich-based terminal UI rendering |
| `logging.py` | JSON structured logging setup |
| `trace.py` | Trace file operations |
| `locking.py` | File locking for safe concurrent access |
| `security.py` | File permission hardening |
| `doctor.py` | Diagnostics and health checks |
| `errors.py` | User-facing error messages |
| `time_utils.py` | Timezone handling utilities |

## Key Patterns

### 1. Configuration Pattern

All configuration flows through `Config` dataclass (frozen for immutability):

```python
from kmi_manager_cli.config import load_config

config = load_config()  # Loads from .env or environment
# Access: config.dry_run, config.proxy_listen, etc.
```

**Important**: `dry_run=True` (default) simulates all upstream requests. Set `KMI_DRY_RUN=0` for live traffic.

### 2. State Management Pattern

State is loaded once, mutated in memory, and saved via `StateWriter`:

```python
from kmi_manager_cli.state import load_state, save_state
from kmi_manager_cli.keys import load_auths_dir

registry = load_auths_dir(config.auths_dir, config.upstream_base_url, ())
state = load_state(config, registry)  # Auto-migrates schema
# ... mutate state ...
save_state(config, state)  # Atomic write with file locking
```

In async contexts (proxy), use `StateWriter` for debounced saves:
```python
state_writer = StateWriter(config=config, state=state, lock=asyncio.Lock())
await state_writer.mark_dirty()  # Debounced write
```

### 3. Key Selection Pattern

```python
from kmi_manager_cli.rotation import select_key_for_request

key = select_key_for_request(
    registry, state, 
    auto_rotate=True,  # Use round-robin
    health=health_map,  # From get_health_map()
    require_usage_ok=True,  # Strict mode
    fail_open_on_empty_cache=True
)
```

### 4. Health Check Pattern

```python
from kmi_manager_cli.health import get_health_map

health = get_health_map(config, registry, state)
# health["key_label"].status: "healthy" | "warn" | "blocked" | "exhausted"
# health["key_label"].remaining_percent: 0-100 float
```

### 5. Testing Pattern

Tests use simple dataclass instantiation:

```python
def test_rotation():
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ],
        active_index=0
    )
    state = State(active_index=0)
    # ... test logic ...
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KMI_AUTHS_DIR` | `_auths` | Directory containing auth files |
| `KMI_PROXY_LISTEN` | `127.0.0.1:54123` | Proxy bind address |
| `KMI_PROXY_BASE_PATH` | `/kmi-rotor/v1` | Proxy URL prefix |
| `KMI_UPSTREAM_BASE_URL` | `https://api.kimi.com/coding/v1` | Upstream API URL |
| `KMI_DRY_RUN` | `1` | Simulate requests (default: True) |
| `KMI_AUTO_ROTATE_ALLOWED` | `0` | Enable auto-rotation |
| `KMI_WRITE_CONFIG` | `1` | Write selected key to ~/.kimi/config.toml |
| `KMI_PROXY_TOKEN` | `""` | Token for remote proxy auth |
| `KMI_REQUIRE_USAGE_BEFORE_REQUEST` | `0` | Block requests without cached usage |
| `KMI_FAIL_OPEN_ON_EMPTY_CACHE` | `1` | Allow requests when cache cold |
| `KMI_ENFORCE_FILE_PERMS` | `1` | Harden file permissions to 600/700 |
| `KMI_ROTATE_INCLUDE_WARN` | `0` | Include 'warn' status keys in auto-rotation |

### Auth File Formats

**`.env` format:**
```bash
KMI_API_KEY=sk-your-key
KMI_KEY_LABEL=production-alpha
KMI_KEY_PRIORITY=10
KMI_KEY_DISABLED=false
KMI_UPSTREAM_BASE_URL=https://api.kimi.com/coding/v1
```

**`.toml` format** (Kimi CLI config style):
```toml
[providers.moonshot-ai]
api_key = "sk-your-key"
base_url = "https://api.kimi.com/coding/v1"
```

## State Schema

```python
@dataclass
class State:
    schema_version: int = 1
    active_index: int = 0        # Currently selected key index
    rotation_index: int = 0      # Round-robin position
    auto_rotate: bool = False    # Auto-rotation enabled
    last_health_refresh: Optional[str] = None  # ISO timestamp
    keys: dict[str, KeyState] = field(default_factory=dict)

@dataclass  
class KeyState:
    last_used: Optional[str] = None      # ISO timestamp
    request_count: int = 0
    error_401: int = 0
    error_403: int = 0
    error_429: int = 0
    error_5xx: int = 0
    exhausted_until: Optional[str] = None  # ISO timestamp
    blocked_until: Optional[str] = None    # ISO timestamp
    blocked_reason: Optional[str] = None
```

## Common Tasks for Agents

### Adding a New Configuration Option

1. Add default constant in `config.py` (line ~11-44)
2. Add field to `Config` dataclass (line ~107-143)
3. Add loading logic in `load_config()` (line ~159-294)
4. Add test in `tests/test_config.py`

### Adding a New CLI Command

1. Add function in `cli.py` with `@app.command()` decorator
2. Use `_load_config_or_exit()` for config loading
3. Use `typer.echo()` for output, `rich` console for formatted output
4. Add test in `tests/test_cli_*.py`

### Modifying Rotation Logic

1. Edit `rotation.py` - main logic in:
   - `rotate_manual()` for manual rotation
   - `select_key_round_robin()` for auto-rotation
2. Update `_is_eligible()` if changing eligibility criteria
3. Tests in `tests/test_rotation.py`

### Adding Health Check Logic

1. Edit `health.py` - main functions:
   - `fetch_usage()` - API call to /usages endpoint
   - `score_key()` - Convert usage to status
   - `get_health_map()` - Build health for all keys
2. `HealthInfo` dataclass holds all health data

### Working with the Proxy

The proxy (`proxy.py`) has these key components:

- **`create_app()`**: Builds FastAPI app with lifespan management
- **`ProxyContext`**: Shared state between requests
- **`RateLimiter`/`KeyedRateLimiter`**: Token bucket rate limiting
- **`StateWriter`**: Debounced async state persistence
- **`TraceWriter`**: Async trace logging

**Request flow:**
1. `_authorize_request()` - Token validation
2. `rate_limiter.allow()` - Global rate limit check
3. `_select_key()` - Choose API key
4. `key_rate_limiter.allow()` - Per-key rate limit check
5. HTTP request to upstream with retry logic
6. Response handling with error detection
7. State update and trace write

## Testing Guidelines

### Running Tests

```bash
# All tests
python -m pytest tests/ -q

# With coverage
python -m pytest tests/ --cov=kmi_manager_cli --cov-report=term-missing

# Specific module
python -m pytest tests/test_rotation.py -v
```

### Coverage Requirements

- Minimum 95% coverage enforced in `pyproject.toml`
- UI modules (`ui.py`, `trace_tui.py`) are excluded from coverage
- Branch coverage is enabled

### Writing Tests

- Use descriptive function names: `test_<function>_<scenario>`
- Create minimal `Registry` and `State` instances
- Test edge cases: empty registries, tied scores, blocked keys
- Use parametrization for multiple similar cases

## File Locations

| Purpose | Path |
|---------|------|
| Source code | `src/kmi_manager_cli/` |
| Tests | `tests/` |
| Configuration | `.env` (project root) |
| Auth files | `_auths/` (or `KMI_AUTHS_DIR`) |
| State | `~/.kmi/state.json` |
| Logs | `~/.kmi/logs/kmi.log` |
| Traces | `~/.kmi/trace/trace.jsonl` |
| Proxy daemon log | `~/.kmi/logs/proxy.out` |

## Security Considerations

1. **Never log full API keys** - Use `mask_key()` from `keys.py`
2. **File permissions** - `security.py` enforces 600/700 on POSIX
3. **Proxy token** - Required for remote bindings, use `secrets.compare_digest()`
4. **TLS** - Enforced for remote proxy unless explicitly disabled
5. **Allowlist** - Upstream URLs validated against `KMI_UPSTREAM_ALLOWLIST`

## Async Patterns

The proxy uses modern Python async patterns:

```python
# State lock prevents race conditions
async with ctx.state_lock:
    ctx.state.active_index = new_index

# Background task for cleanup
background = BackgroundTask(_close_stream, stream_ctx, client)
return StreamingResponse(..., background=background)

# Debounced writes
async def mark_dirty(self):
    self._dirty = True
    self._flush.set()  # Trigger background save
```

## Troubleshooting Common Issues

### "No API keys found"
- Check `_auths/` directory exists and contains `.env` or `.toml` files
- Verify `KMI_API_KEY` is set in auth files

### Proxy won't start
- Check if port already in use: `lsof -i :54123`
- For remote binding: ensure `KMI_PROXY_ALLOW_REMOTE=1` and `KMI_PROXY_TOKEN` set

### Rotation not working
- Check dry-run mode: `KMI_DRY_RUN=0` required for live rotation
- Verify keys aren't blocked/exhausted in state

### Tests failing
- Ensure `.env` doesn't have values that break tests
- Check Python version >= 3.9

## Code Style

- **Ruff** for linting (all checks currently pass)
- Type hints required for all functions
- Docstrings encouraged but not strictly enforced
- Prefer dataclasses over dicts for structured data
- Use `pathlib.Path` for file operations
- Use `from __future__ import annotations` for forward references
