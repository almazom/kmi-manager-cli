# Card 01: KMI Manager CLI - Config + CLI scaffold

| Field | Value |
|-------|-------|
| **ID** | KMI-01 |
| **Story Points** | 3 |
| **Depends On** | - |
| **Sprint** | 1 |

## User Story

> As an operator, I want a global `kmi --help` command so that I can discover rotation and trace features quickly.

## Context

Read before starting:
- [requirements.md#1-goals--success-criteria](../requirements.md)
- [ui-flow.md#user-journey](../ui-flow.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git (env overrides + config patterns)

## Must Have

- [ ] Global CLI entrypoint `kmi --help` with core flags listed
- [ ] `.env` loader and config schema with defaults
- [ ] No secrets in code (env-only)

## Instructions

### Step 1: Define project layout

```bash
# Proposed layout (Python/typer)
mkdir -p src/kmi_manager_cli
mkdir -p src/kmi_manager_cli/commands
```

### Step 2: Create config model + .env loader

```python
# File: src/kmi_manager_cli/config.py
# - load .env
# - validate required env vars
# - default values for KMI_AUTHS_DIR, KMI_PROXY_BASE_PATH, KMI_UPSTREAM_BASE_URL
```

### Step 3: Create CLI entrypoint

```python
# File: src/kmi_manager_cli/cli.py
# - typer app
# - flags: --rotate, --auto_rotate, --trace, --all
# - default command prints help
```

### Step 4: Verification

```bash
# Verify entrypoint path and help output
python -m kmi_manager_cli.cli --help
```

### Step 5: Test

```bash
# Placeholder (define real tests in Card 10)
pytest -q
```

## Acceptance Criteria

- [ ] `kmi --help` shows all required flags
- [ ] `.env` defaults applied when unset
- [ ] No secrets appear in logs or stdout

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
