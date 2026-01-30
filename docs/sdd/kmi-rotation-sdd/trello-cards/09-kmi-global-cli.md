# Card 09: KMI Manager CLI - Global install + kmi --help

| Field | Value |
|-------|-------|
| **ID** | KMI-09 |
| **Story Points** | 2 |
| **Depends On** | 08 |
| **Sprint** | 4 |

## User Story

> As a user, I want `kmi --help` to work globally from PATH.

## Context

Read before starting:
- [requirements.md#1-goals--success-criteria](../requirements.md)
- [requirements.md#3-cli-commands--flags](../requirements.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git

## Must Have

- [ ] CLI installed as `kmi` via package entrypoint
- [ ] `kmi --help` works globally
- [ ] Version and config path shown in help

## Instructions

### Step 1: Add package entrypoint

```toml
# File: pyproject.toml
# [project.scripts]
# kmi = "kmi_manager_cli.cli:main"
```

### Step 2: Provide help output

```python
# File: src/kmi_manager_cli/cli.py
# - define app = typer.Typer(help=...)
# - include version + config paths
```

### Step 3: Verification

```bash
pip install -e .
kmi --help
```

## Acceptance Criteria

- [ ] `kmi` is available in PATH after install
- [ ] Help includes rotate/auto_rotate/trace/all
- [ ] Help shows config defaults

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
