# Card 03: KMI Manager CLI - Proxy routing + unique base path

| Field | Value |
|-------|-------|
| **ID** | KMI-03 |
| **Story Points** | 4 |
| **Depends On** | 02 |
| **Sprint** | 1 |

## User Story

> As an operator, I want a local proxy with a unique base path so each request can be routed to a selected key.

## Context

Read before starting:
- [requirements.md#5-proxy-routing](../requirements.md)
- [gaps.md#gap-002-unique-proxy-base-pathport](../gaps.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git (Kimi provider uses `KIMI_BASE_URL`)

## Must Have

- [ ] Proxy listens on `KMI_PROXY_LISTEN` + `KMI_PROXY_BASE_PATH`
- [ ] Any sub-path is forwarded to `KMI_UPSTREAM_BASE_URL`
- [ ] Inject `Authorization: Bearer <key>`

## Instructions

### Step 1: Create proxy server skeleton

```python
# File: src/kmi_manager_cli/proxy.py
# - FastAPI or aiohttp server
# - Mount router at KMI_PROXY_BASE_PATH
```

### Step 2: Forward requests

```python
# File: src/kmi_manager_cli/proxy.py
# - accept any path: /{path:path}
# - forward method, headers, body to upstream
# - replace Authorization header with selected key
```

### Step 3: Wire into CLI

```python
# File: src/kmi_manager_cli/cli.py
# - command: kmi proxy (optional)
# - start server and print listen URL
```

### Step 4: Verification

```bash
# Start proxy
kmi proxy

# Test upstream model list via proxy
curl -s http://127.0.0.1:54123/kmi-rotor/v1/models | head -20
```

## Acceptance Criteria

- [ ] Proxy forwards requests to upstream
- [ ] Authorization header always uses selected key
- [ ] Unique base path is configurable

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
