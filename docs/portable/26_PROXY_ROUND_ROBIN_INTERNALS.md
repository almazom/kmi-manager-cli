# Proxy + Round‑Robin Rotation (Under the Hood)

This document explains **exact internal behavior** of the proxy and the round‑robin key selection. It is written for AI agents or operators who need precise mechanics.

---

## 1) Proxy request lifecycle (step‑by‑step)

When a request hits the proxy route:

1) **Authorize**
   - If `KMI_PROXY_TOKEN` is empty: open access.
   - If set: request must include:
     - `Authorization: Bearer <token>` or
     - `x-kmi-proxy-token: <token>`
   - Fail → `401 Unauthorized`.

2) **Global rate limit**
   - `KMI_PROXY_MAX_RPS` / `KMI_PROXY_MAX_RPM` are enforced.
   - Fail → `429 Proxy rate limit exceeded`.

3) **Key selection (rotation)**
   - Uses `select_key_for_request(...)` (see section 3).
   - If no eligible key → `503` with remediation message.

4) **Per‑key rate limit**
   - `KMI_PROXY_MAX_RPS_PER_KEY` / `KMI_PROXY_MAX_RPM_PER_KEY`.
   - Fail → revert indices, mark state dirty, return `429`.

5) **Build upstream request**
   - Removes hop‑by‑hop headers.
   - Removes `host`, `content-length`, `authorization`, `x-kmi-proxy-token`.
   - Adds `Authorization: Bearer <selected_key>`.

6) **Extract prompt hint**
   - Reads JSON body; extracts last user message/prompt.
   - Stores:
     - `prompt_hint` (trimmed text)
     - `prompt_head` (first word)

7) **Dry‑run branch** (`KMI_DRY_RUN=1`)
   - No upstream request.
   - Records state + log + trace.
   - Returns JSON with `dry_run: true`.

8) **Live branch**
   - Sends request via `httpx.AsyncClient.stream`.
   - Handles retries (see section 5).
   - Updates state counters + exhausts keys on errors.
   - Writes trace + logs.
   - Returns upstream response (streaming if possible).

---

## 2) Header handling

- Hop‑by‑hop headers are stripped (`connection`, `transfer-encoding`, etc.).
- `Authorization` from client is removed and replaced with the selected key.
- `x-kmi-proxy-token` is not forwarded upstream.

---

## 3) Rotation logic (auto vs manual)

### Eligibility rules (`_is_eligible`)
A key is **ineligible** if:
- `key.disabled == True`
- `state.keys[label].error_401 > 0` (401 means invalid)
- `state.keys[label].exhausted_until` is in the future
- `state.keys[label].blocked_until` is in the future (payment/auth blocklist)
- Health status is `blocked` or `exhausted` (when health info is used)

### Auto‑rotation (proxy per‑request)

Used when:
- `state.auto_rotate == True` **and**
- `KMI_AUTO_ROTATE_ALLOWED == 1`

Algorithm (`select_key_round_robin`):
1) Use `state.rotation_index` as starting point.
2) If health map exists:
   - Scan keys from `rotation_index` forward.
   - Prefer keys with `status == healthy` AND eligible.
3) If none found, scan all keys for any eligible.
4) On selection:
   - `state.rotation_index = (idx + 1) % total`
   - `mark_last_used()` for the key

### Manual rotation

Command:
- `kmi rotate` or `kmi --rotate`

Scoring logic:
- Status rank: healthy < warn < other
- Remaining quota (descending)
- Error rate (ascending)
- Tie‑breakers can keep current or rotate to next if `KMI_ROTATE_ON_TIE=1`

Manual rotation is **not** used per‑request; it only changes the active key and optional config.

### Non‑auto selection in proxy

If auto‑rotation is off:
- Use `registry.active_key` if eligible
- Else find next eligible (`next_healthy_index`)
- Update `state.active_index`

---

## 4) State updates

State file:
- `~/.kmi/state.json`

On each request:
- `record_request()` increments counters
- Errors increment:
  - `error_401`, `error_403`, `error_429`, `error_5xx`
- `mark_last_used()` updates timestamp
- Payment/billing errors set:
  - `blocked_until`
  - `blocked_reason` (e.g., `payment_required`)

State writes:
- Debounced by `StateWriter` (default 50ms)
- Uses file lock + atomic write

Important notes:
- A key with `error_401 > 0` is effectively disabled until state is reset.
- `exhausted_until` is UTC timestamp; eligibility returns when it expires.
- `blocked_until` is UTC timestamp; eligibility returns when it expires or is cleared.
- `last_health_refresh` is set by background health refresh.

---

## 5) Retry + cooldown behavior

### Retry rules
- Retries are enabled when `KMI_PROXY_RETRY_MAX > 0`.
- Exponential backoff: `base_ms * (2 ** attempt)`.

### When retry happens
- Network errors (`httpx.HTTPError`)
- Responses `429` or any `5xx`

### Cooldown / exhaustion
When upstream response is:
- `403` or `429` or `5xx` → key is marked exhausted.
- `402` or payment/billing tokens → key is blocked (payment required).

Cooldown duration:
- Default: `KMI_ROTATION_COOLDOWN_SECONDS`
- If `429` and `Retry-After` header exists → use it
- If `5xx` → cooldown capped at 60s

---

## 6) Trace + logging

### Trace file
- `~/.kmi/trace/trace.jsonl`
- Fields include:
  - `prompt_hint`, `prompt_head`
  - `key_label`, `rotation_index`, `status`, etc.
  - `error_code` may be `payment_required` on billing errors

### Logging
- `~/.kmi/logs/kmi.log`
- JSON logs with `proxy_request`, `proxy_upstream_error`, etc.

### Queue writer note
The proxy starts a `TraceWriter` queue, but **currently writes traces directly** via `append_trace(...)`. This means trace writes are synchronous in the request path.

---

## 7) Health map usage

In auto‑rotation (or strict usage) mode the proxy uses cached health data:

- `/usages` calls happen in a **background loop**, not on the request path
- Cache refresh interval: `KMI_USAGE_CACHE_SECONDS` (default 600s)
- `healthy` keys are preferred in round‑robin; fallback to any eligible
- `last_health_refresh` timestamp is persisted in state

### Strict usage check (optional)
- `KMI_REQUIRE_USAGE_BEFORE_REQUEST=1` requires `usage_ok` in cache.
- `KMI_FAIL_OPEN_ON_EMPTY_CACHE=1` allows requests while cache warms.

---

## 8) Dry‑run behavior

When `KMI_DRY_RUN=1`:
- No upstream HTTP calls
- Proxy still records state/log/trace
- Response includes `dry_run: true` and selected key

---

## 9) Streaming

- Uses `httpx.AsyncClient.stream`
- If response is not fully consumed, returns a streaming response
- Closes stream in a background task

---

## 10) Quick mental model

```
Request -> Auth -> Rate Limit -> Select Key -> Upstream -> Update State -> Trace/Log
                      |             |
                      |             +-> rotation_index++ (auto)
                      +-> key rate limit

Background loop -> /usages refresh -> update cache + last_health_refresh
                -> recheck blocked keys (limited per interval)
```
