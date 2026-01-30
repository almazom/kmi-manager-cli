# KMI Manager CLI - Functional Requirements

> Status: IN_PROGRESS | Last updated: 2026-01-29 11:14:26 MSK

## 1. Goals & Success Criteria

### 1.1 Primary Goals
- System MUST provide a globally available CLI named `kmi` (e.g., `kmi --help`).
- System MUST support manual rotation (`kmi --rotate`) and automatic round-robin rotation (`kmi --auto_rotate`).
- System MUST provide a trace window (`kmi --trace`) to visualize per-request routing.
- System MUST maintain secrets outside code (only `.env` + `_auths/`).

### 1.2 Success Criteria
- 95%+ confidence that rotation is round-robin for the last N requests (default N=200) is displayed.
- A dashboard view shows key health, last used time, and error counts.
- Proxy routing works with Kimi CLI using `KIMI_BASE_URL` + `KIMI_API_KEY` overrides.

---

## 2. Scope

### 2.1 In-Scope
- CLI wrapper `kmi` with flags: `--rotate`, `--auto_rotate`, `--trace`, `--all`, `--health`, `--current`, `--status`.
- Local proxy with unique base path and port.
- Key registry from `_auths/` + `.env`.
- Health/usage collection per key (quota + errors).
- Trace logs (JSONL) + TUI view.

### 2.2 Out of Scope
- GUI/Web UI (optional later).
- Automatic account creation.
- Multi-tenant access control.

---

## 3. CLI Commands & Flags

### 3.1 Base
- `kmi --help`: show usage and options.

### 3.2 Rotation
- `kmi --rotate` or `kmi rotate`: select the **most resourceful** eligible key (highest remaining quota, lowest error rate) and show dashboard. If the current key already ranks best, the rotation is skipped with a reason.
- `kmi --auto_rotate` or `kmi rotate auto`: enable round-robin per request.
- `kmi rotate off`: disable auto-rotation.

### 3.3 Observability
- `kmi --trace` or `kmi trace`: real-time trace view; exits on Ctrl+C.
- `kmi --all`, `kmi --health`, or `kmi health`: show health of all keys without rotating.
- `kmi --current`: show health for the current account only.

### 3.4 Status
- `kmi --status` or `kmi status`: show active index, rotation index, and auto-rotate flag.

---

## 4. Key Storage & Rotation Rules

### 4.1 Key Storage
- `_auths/` directory contains per-key files (`*.env`) with:
  - `KMI_API_KEY`
  - `KMI_KEY_LABEL`
  - `KMI_KEY_PRIORITY` (optional)
  - `KMI_KEY_DISABLED` (optional)
- A registry is built from `_auths/` at startup.

### 4.2 Rotation Policy
- Manual rotation selects the **most resourceful** eligible key (prefers `healthy` status, higher remaining quota, lower error rate). If the current key ties for best, rotation is skipped with a reason.
- Auto rotation selects a healthy key per request; unhealthy keys are skipped.
- If all keys are unhealthy, proxy returns an error with remediation hints.

### 4.3 Round Robin Rotation Principle (MANDATORY)
- Maintain a pool of valid keys for the same service.
- Sequential selection per request: Key A → Key B → Key C → ...
- Cyclic reset: loop back to the first key after the last.
- Error handling: on `429` or `403`, mark key as **exhausted** and skip for a cooldown period.

---

## 5. Proxy Routing

### 5.1 Unique Proxy API
- Proxy MUST listen on a unique path, e.g. `http://127.0.0.1:54123/kmi-rotor/v1`.
- Base path MUST be configurable via `.env`.

### 5.2 Transparent Routing
- Proxy MUST accept any sub-path (e.g. `/chat/completions`, `/models`, `/usages`, `/search`, `/fetch`).
- Proxy MUST forward to upstream `KMI_UPSTREAM_BASE_URL` and inject `Authorization: Bearer <key>`.

### 5.3 Compatibility
- Must support Kimi CLI and Kimi provider behavior:
  - OpenAI-style chat completions (`/chat/completions`)
  - Model listing (`/models`)
  - Usage endpoint (`/usages`) for health

---

## 6. Health & Usage

### 6.1 Data Sources
- Usage endpoint: `GET {base_url}/usages` with bearer key.
- Error telemetry: 401/403/429/5xx counts from proxy logs.

### 6.2 Health Scoring
- `healthy` if usage remaining >= 20% and error rate < 5%.
- `warn` if usage remaining < 20% or recent 429/5xx spikes.
- `blocked` if 401/403 or usage remaining <= 0.
- `exhausted` (temporary) if 429/403 seen; skip until cooldown expires.

---

## 7. Traceability & Confidence

### 7.1 Trace Logs
- JSONL log per request with fields:
  - `ts_msk`, `request_id`, `key_label`, `key_hash`, `endpoint`, `status`, `latency_ms`, `error_code`, `rotation_index`.

### 7.2 Trace Window
- TUI view: scrolling list of recent requests + summary panel.
- Summary panel shows key distribution and **confidence %**.

### 7.3 Confidence Metric
- Rolling window (default 200 requests).
- Compute expected uniform distribution; confidence = 100% - max deviation %.
- Warn if confidence < 95%.

---

## 8. Configuration & Secrets

### 8.1 .env Required
- `KMI_AUTHS_DIR` (default: `_auths`)
- `KMI_PROXY_LISTEN` (default: `127.0.0.1:54123`)
- `KMI_PROXY_BASE_PATH` (default: `/kmi-rotor/v1`)
- `KMI_UPSTREAM_BASE_URL` (default: `https://api.kimi.com/coding/v1`)
- `KMI_STATE_DIR` (default: `~/.kmi`)

### 8.2 No Hardcoding
- No API keys inside code or repo.
- All secrets only in `.env` and `_auths/`.

---

## 9. Logging

- Structured JSON logs when possible.
- Timestamps in MSK.
- Log file location: `${KMI_STATE_DIR}/logs/kmi.log`.
- Trace logs separate: `${KMI_STATE_DIR}/trace/trace.jsonl`.

---

## 10. Error Handling

- If `_auths/` missing or empty, CLI must exit with actionable instructions.
- If proxy cannot reach upstream, show retry suggestion and mark key as warn.
- If all keys are blocked, return HTTP 503 with remediation steps.
- Cooldown policy: 429/403 marks key as exhausted; re-enable after cooldown.

---

## 11. Compliance & Policy

- Operators MUST review API provider SLA/ToS regarding key pooling/round-robin.
- If key pooling is prohibited, the system MUST support disabling auto rotation.
- Proxy SHOULD support optional rate limiting and retry backoff to respect provider limits.
- Remote proxy access MUST be an explicit opt-in and protected (token or allowlist).

---

## 12. Non-Functional Requirements

- Latency overhead per proxy request <= 30 ms (local).
- Supports >= 20 keys.
- No secrets in stdout (mask keys).

---

## 13. References

- Kimi CLI env overrides: `KIMI_API_KEY`, `KIMI_BASE_URL`
- Kimi CLI usage endpoint: `{base_url}/usages`
- Kimi chat provider uses OpenAI-style `/chat/completions`


---

## 14. Upstream Kimi CLI insights (for implementation)

- Env overrides used by Kimi CLI: `KIMI_API_KEY`, `KIMI_BASE_URL` (see `src/kimi_cli/llm.py`).
- Kimi provider defaults to OpenAI-style endpoints and base URL when not overridden (see `packages/kosong/src/kosong/chat_provider/kimi.py`).
- Usage endpoint available at `{base_url}/usages` (see `src/kimi_cli/ui/shell/usage.py`).

Reference repo: https://github.com/MoonshotAI/kimi-cli.git
