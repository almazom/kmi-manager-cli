# 🧟 Zombie Code Hunter Report

**Project:** KMI Manager CLI  
**Date:** 2026-02-04  
**Scope:** Security vulnerabilities, async safety, resource management, and code quality issues

---

## 🔴 Critical Security Vulnerabilities

### 1. **Token Validation Bypass via Header Case Sensitivity**

**Location:** `src/kmi_manager_cli/proxy.py:587-596`

**Issue:** The `_authorize_request` function extracts the token from the `Authorization` header with case-insensitive prefix matching (`auth_header.lower().startswith("bearer ")`), but then splits on a single space. This could lead to subtle parsing issues with malformed headers.

```python
def _authorize_request(request: Request, token: str) -> bool:
    if not token:
        return True
    auth_header = request.headers.get("authorization", "")  # HTTP headers are case-insensitive
    provided = ""
    if auth_header.lower().startswith("bearer "):
        provided = auth_header.split(" ", 1)[1].strip()
    if not provided:
        provided = request.headers.get("x-kmi-proxy-token", "").strip()
    return secrets.compare_digest(provided, token)  # ✅ Timing-safe comparison
```

**Risk:** Low-Medium  
**Mitigation:** The `secrets.compare_digest` is correctly used for timing attack prevention. However, consider normalizing the token extraction logic to handle edge cases like multiple spaces.

---

### 2. **Missing Client Certificate Validation**

**Location:** `src/kmi_manager_cli/proxy.py:621`, `src/kmi_manager_cli/health.py:254-256`

**Issue:** The HTTP client configuration does not specify `verify=True` explicitly, relying on defaults. While httpx defaults to verification, this is implicit rather than explicit.

```python
ctx.http_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=100, max_keepalive_connections=20))
```

**Risk:** Low  
**Mitigation:** Explicitly set `verify=True` and consider adding cert pinning for the upstream API.

---

### 3. **API Key Logging Exposure in Headers (Partial)**

**Location:** `src/kmi_manager_cli/proxy.py:142-150`

**Issue:** The `_build_upstream_headers` function properly strips sensitive headers, but the trace logging includes `key_hash` which could potentially be correlated with actual keys.

```python
def _build_upstream_headers(request_headers: Iterable[tuple[str, str]], api_key: str) -> dict[str, str]:
    headers = _filter_hop_by_hop_headers(request_headers)
    for key in list(headers):
        if key.lower() in {"host", "content-length", "authorization", "x-kmi-proxy-token"}:
            headers.pop(key, None)
    headers["authorization"] = f"Bearer {api_key}"
    return headers
```

**Risk:** Low  
**Status:** ✅ Properly handled - Authorization header is stripped from client request before adding upstream key.

---

## 🔴 Critical Async/Resource Bugs

### 1. **HTTP Client Resource Leak in Error Path**

**Location:** `src/kmi_manager_cli/proxy.py:730-735`

**Issue:** When the proxy is used without the lifespan manager (tests only path), an httpx client is created lazily but never properly closed on all error paths.

```python
client = ctx.http_client
if client is None:
    # Lazy initialization for tests that don't use lifespan
    client = httpx.AsyncClient(timeout=30.0)
    ctx.http_client = client
```

**Risk:** Medium  
**Impact:** Resource leak in test scenarios only. Production uses lifespan management.  
**Mitigation:** Ensure the test path also uses proper context management.

---

### 2. **Missing State Lock During Key Selection Rollback**

**Location:** `src/kmi_manager_cli/proxy.py:666-670`

**Issue:** When a key fails the per-key rate limiter, the state is rolled back. The rollback and dirty marking happen correctly, but there's a potential race if another request has already modified the state.

```python
if not await ctx.key_rate_limiter.allow(key_label):
    async with ctx.state_lock:
        ctx.state.active_index = prev_active
        ctx.state.rotation_index = prev_rotation
    await ctx.state_writer.mark_dirty()
```

**Risk:** Low  
**Mitigation:** Consider holding the lock for the entire selection + rate limit check sequence, though this would reduce throughput.

---

### 3. **Potential Infinite Loop in Health Refresh Loop**

**Location:** `src/kmi_manager_cli/proxy.py:364-375`

**Issue:** The `_health_refresh_loop` catches all exceptions and continues. If there's a persistent error condition, this could lead to rapid error loops.

```python
async def _health_refresh_loop(ctx: ProxyContext) -> None:
    logger = get_logger(ctx.config)
    while not ctx.health_stop.is_set():
        try:
            await _maybe_refresh_health(ctx)
            await _maybe_recheck_blocked(ctx)
        except Exception as exc:  # 🔴 Bare except
            log_event(logger, "health_refresh_error", error=str(exc))
        try:
            await asyncio.wait_for(ctx.health_stop.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
```

**Risk:** Low-Medium  
**Mitigation:** Add exponential backoff for repeated errors and circuit breaker pattern.

---

### 4. **State Writer Task Not Awaiting on Stop**

**Location:** `src/kmi_manager_cli/proxy.py:420-424`

**Issue:** The `stop()` method cancels but may not properly await the background task if it's in the middle of a write.

```python
async def stop(self) -> None:
    self._stop.set()
    self._flush.set()
    if self._task:
        await self._task  # This waits but doesn't handle pending writes atomically
```

**Risk:** Low  
**Mitigation:** Consider adding a final synchronous write before shutdown completes.

---

## 🟡 Medium Risk Issues

### 1. **Broad Exception Handling in Parsing Functions**

**Locations:**
- `src/kmi_manager_cli/ui.py:245, 255, 280, 290`
- `src/kmi_manager_cli/cli.py:751`
- `src/kmi_manager_cli/time_utils.py:34`
- `src/kmi_manager_cli/security.py:24, 58`

**Issue:** Multiple instances of bare `except Exception:` swallow all exceptions, potentially masking bugs:

```python
# ui.py:245
try:
    seconds = int(parts[-1].rstrip("s"))
except Exception:
    return raw
```

**Risk:** Medium  
**Impact:** Makes debugging difficult, can mask programming errors  
**Recommendation:** Use specific exception types (`ValueError`, `TypeError`, etc.) where possible.

---

### 2. **File Lock Not Released on Windows Exception**

**Location:** `src/kmi_manager_cli/locking.py:19-46`

**Issue:** On Windows (non-fcntl), if an exception occurs during the `yield`, the lock file handle may not be properly cleaned up:

```python
@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    lock_path = _lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        if fcntl:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        else:
            fd = None
            while fd is None:
                try:
                    fd = os.open(str(lock_path) + ".win", os.O_CREAT | os.O_EXCL | os.O_RDWR)
                except FileExistsError:
                    time.sleep(0.05)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                if fd is not None:
                    os.close(fd)
                    try:
                        os.unlink(str(lock_path) + ".win")
                    except FileNotFoundError:
                        pass
```

**Risk:** Low-Medium  
**Issue:** If an exception occurs in the `finally` block on Windows (e.g., permissions issue), the lock file remains.  
**Mitigation:** Wrap the cleanup in try-except blocks.

---

### 3. **Potential Unbounded Growth in KeyedRateLimiter**

**Location:** `src/kmi_manager_cli/proxy.py:519-546`

**Issue:** The `KeyedRateLimiter` creates a new deque for each unique key:

```python
async def allow(self, key: str) -> bool:
    if self.max_rps <= 0 and self.max_rpm <= 0:
        return True
    async with self.lock:
        now = time.time()
        bucket = self.recent.setdefault(key, deque(maxlen=10000))
```

**Risk:** Low  
**Impact:** If many unique keys are used over time, the `self.recent` dict grows unbounded.  
**Mitigation:** Add periodic cleanup of old/deleted keys.

---

### 4. **Race Condition in Health Cache Update**

**Location:** `src/kmi_manager_cli/proxy.py:298-315`

**Issue:** The health cache timestamp check and update are not atomic:

```python
async def _maybe_refresh_health(ctx: ProxyContext) -> None:
    interval = ctx.config.usage_cache_seconds
    if interval <= 0:
        return
    now = time.time()
    async with ctx.state_lock:
        if ctx.health_cache_ts and (now - ctx.health_cache_ts) < interval:
            return
    health = await asyncio.to_thread(get_health_map, ctx.config, ctx.registry, ctx.state)
    async with ctx.state_lock:
        ctx.health_cache = health
        ctx.health_cache_ts = now
```

**Risk:** Low  
**Issue:** Multiple concurrent requests could trigger simultaneous health fetches. The check-then-act pattern could allow redundant work.  
**Mitigation:** Use a lock or atomic compare-and-swap pattern.

---

### 5. **Trace File Permission Enforcement Delay**

**Location:** `src/kmi_manager_cli/trace.py:61-81`

**Issue:** File permissions are enforced after writing, creating a small window where the file may have insecure permissions:

```python
def append_trace(config: Config, entry: dict) -> None:
    # ...
    with file_lock(path):
        _rotate_trace_if_needed(path, config.trace_max_bytes, config.trace_max_backups)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    logger = get_logger(config)
    ensure_secure_permissions(path, logger, "trace_file", is_dir=False, enforce=config.enforce_file_perms)
```

**Risk:** Low  
**Mitigation:** Use `os.open()` with specific mode flags before writing.

---

### 6. **Potential Blocking I/O in Async Context**

**Location:** `src/kmi_manager_cli/state.py:167-179`

**Issue:** `save_state` uses synchronous file I/O that could block the event loop:

```python
def save_state(config: Config, state: State) -> None:
    path = _state_path(config)
    payload = json.dumps(state.to_dict(), indent=2) + "\n"
    with file_lock(path):
        atomic_write_text(path, payload)
    # ...
```

**Risk:** Low  
**Impact:** Called via `asyncio.to_thread()` in most cases, but direct calls in async code could block.  
**Status:** ✅ Mitigated - StateWriter uses `asyncio.to_thread()` wrapper.

---

## 🔍 Suspicious Patterns Needing Verification

### 1. **Retry Logic May Double-Count State Updates**

**Location:** `src/kmi_manager_cli/proxy.py:737-764`

**Issue:** When a request is retried, state updates (via `record_request`) may be called multiple times for the same logical request if implemented incorrectly. Current code looks correct, but should be verified.

---

### 2. **Stream Context Not Properly Closed on 5xx Response**

**Location:** `src/kmi_manager_cli/proxy.py:755-764`

The code properly closes the stream context on retry:

```python
if resp.status_code in {429} or 500 <= resp.status_code <= 599:
    if attempt < ctx.config.proxy_retry_max:
        await resp.aread()
        await stream_ctx.__aexit__(None, None, None)  # ✅ Properly closed
        stream_ctx = None
```

**Status:** ✅ Correctly implemented

---

### 3. **Email Regex May Match Invalid Addresses**

**Location:** `src/kmi_manager_cli/auth_accounts.py:62`

```python
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
```

**Issue:** This regex is permissive and may match invalid email addresses in file content, leading to false positives in email extraction.

**Risk:** Low  
**Impact:** Cosmetic - used for display only, not for actual communication.

---

### 4. **JSON Parsing Without Schema Validation**

**Location:** `src/kmi_manager_cli/state.py:73-84`

**Issue:** State is loaded from JSON without strict schema validation:

```python
@classmethod
def from_dict(cls, data: dict) -> "State":
    schema_version = int(data.get("schema_version", STATE_SCHEMA_VERSION))
    keys = {label: KeyState(**info) for label, info in data.get("keys", {}).items()}
    return cls(...)
```

**Risk:** Low  
**Impact:** Malformed state files could cause unexpected behavior.  
**Mitigation:** The `_migrate_state` function provides basic handling.

---

## 🛡️ Security Hardening Recommendations

### 1. **Implement Certificate Pinning**

Add optional certificate pinning for the upstream API to prevent MITM attacks:

```python
# Recommended addition to config
KMI_UPSTREAM_CERT_PIN: str = ""  # SHA-256 hash of expected certificate
```

### 2. **Add Request/Response Size Limits**

Currently no explicit size limits on request/response bodies:

```python
# Add to Config
max_request_body_size: int = 10 * 1024 * 1024  # 10MB
max_response_body_size: int = 100 * 1024 * 1024  # 100MB
```

### 3. **Implement Rate Limiting per IP**

The current rate limiters are global or per-key. Add per-client-IP rate limiting for the proxy endpoint.

### 4. **Add HMAC Request Signing (Optional)**

For high-security deployments, support HMAC signing of requests to prevent replay attacks.

### 5. **Audit Logging for Security Events**

Add specific audit events for:
- Failed authentication attempts
- Blocked key usage attempts  
- Permission changes
- Configuration changes

### 6. **Secure Temp File Creation**

**Location:** `src/kmi_manager_cli/locking.py:49-53`

```python
def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")  # Could use more secure permissions
    os.replace(tmp_path, path)
```

**Recommendation:** Create temp files with restrictive permissions (0o600) before writing:

```python
def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)
```

### 7. **Add Request Timeout for Health Checks**

**Location:** `src/kmi_manager_cli/health.py:254-256`

The timeout is hardcoded at 10 seconds. Make it configurable:

```python
resp = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=config.health_check_timeout)
```

### 8. **Implement Connection Pool Limits Validation**

**Location:** `src/kmi_manager_cli/proxy.py:621`

```python
ctx.http_client = httpx.AsyncClient(
    timeout=30.0, 
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
)
```

Add validation that keepalive connections ≤ max connections.

---

## 📊 Summary Statistics

| Category | Count | Severity |
|----------|-------|----------|
| Critical Security | 3 | 🔴 |
| Critical Async/Resource | 4 | 🔴 |
| Medium Risk | 6 | 🟡 |
| Suspicious Patterns | 4 | 🔍 |
| Hardening Recs | 8 | 🛡️ |

### Files Requiring Attention

1. `src/kmi_manager_cli/proxy.py` - Async safety, resource management
2. `src/kmi_manager_cli/locking.py` - Cross-platform file locking
3. `src/kmi_manager_cli/trace.py` - File permission timing
4. `src/kmi_manager_cli/ui.py` - Exception handling specificity
5. `src/kmi_manager_cli/auth_accounts.py` - Email regex validation

---

## ✅ Positive Security Findings

1. **Timing-safe token comparison** using `secrets.compare_digest()` ✅
2. **Proper API key masking** with `mask_key()` function ✅
3. **Atomic file writes** with lock-based synchronization ✅
4. **HTTPS enforcement** for upstream URLs ✅
5. **File permission hardening** with `ensure_secure_permissions()` ✅
6. **Input validation** for upstream URL allowlist ✅
7. **Proper cleanup** in lifespan context manager ✅
8. **State lock usage** prevents race conditions in state updates ✅
9. **Debounced state writes** prevent I/O thrashing ✅
10. **Request body streaming** prevents memory exhaustion ✅

---

*Report generated by 🧟 Zombie Code Hunter - Finding dead code before it finds you.*
