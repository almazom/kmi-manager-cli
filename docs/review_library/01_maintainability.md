# Maintainability Review: KMI Manager CLI

**Review Date:** 2026-02-04  
**Reviewer:** 🧹 Maintainability Anti-Entropy Agent  
**Scope:** Core source files (`src/kmi_manager_cli/`)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total LOC Analyzed | ~4,500 lines |
| Files Reviewed | 14 |
| High-Priority Issues | 8 |
| Medium-Priority Issues | 12 |
| **Overall Grade** | **B** |

The codebase demonstrates solid architectural decisions with clear module separation and good use of dataclasses. However, several files suffer from excessive function length, code duplication, and nested complexity that impact maintainability.

---

## 🔴 High-Priority Issues

### 1. `proxy.py`: The `proxy` nested function (lines 643-880) - **Cyclomatic Complexity: 35+**

**Problem:** The main request handler inside `create_app()` is a 237-line monster with deep nesting (up to 6 levels) and multiple responsibilities:
- Request authorization
- Rate limiting (global + per-key)
- Key selection
- Dry-run handling
- Upstream request with retry logic
- Error detection and payment blocking
- Response streaming
- Trace logging

**Impact:** Extremely difficult to test, reason about, or modify safely.

**Refactoring Recommendation:**

```python
# BEFORE (lines 643-880): Single massive function
async def proxy(path: str, request: Request) -> Response:
    start = time.perf_counter()
    if not _authorize_request(request, ctx.config.proxy_token):
        # ... 230+ more lines

# AFTER: Extract into cohesive functions
async def proxy(path: str, request: Request) -> Response:
    start = time.perf_counter()
    
    # 1. Validation phase
    auth_result = await _validate_request(request, ctx)
    if auth_result:
        return auth_result
    
    # 2. Rate limiting phase
    rate_result = await _check_rate_limits(ctx, path)
    if rate_result:
        return rate_result
    
    # 3. Key selection phase
    key_result = await _select_and_validate_key(ctx, path)
    if isinstance(key_result, Response):
        return key_result
    key_label, api_key, key_record = key_result
    
    # 4. Handle dry-run
    if ctx.config.dry_run:
        return await _handle_dry_run(ctx, request, key_label, key_record, start)
    
    # 5. Execute upstream request
    return await _execute_upstream_request(ctx, request, key_label, api_key, key_record, start)
```

---

### 2. `proxy.py`: Duplicate rate limiting logic

**Problem:** `RateLimiter` (lines 490-516) and `KeyedRateLimiter` (lines 519-547) share nearly identical implementation:

```python
# RateLimiter.allow() - lines 497-516
async def allow(self) -> bool:
    if self.max_rps <= 0 and self.max_rpm <= 0:
        return True
    async with self.lock:
        now = time.time()
        while self.recent and now - self.recent[0] > 60:
            self.recent.popleft()
        if self.max_rpm > 0 and len(self.recent) >= self.max_rpm:
            return False
        if self.max_rps > 0:
            cutoff = now - 1
            rps = 0
            for ts in reversed(self.recent):
                if ts < cutoff:
                    break
                rps += 1
            if rps >= self.max_rps:
                return False
        self.recent.append(now)
        return True

# KeyedRateLimiter.allow() - lines 526-546
async def allow(self, key: str) -> bool:
    if self.max_rps <= 0 and self.max_rpm <= 0:
        return True
    async with self.lock:
        now = time.time()
        bucket = self.recent.setdefault(key, deque(maxlen=10000))
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        # ... identical rps/rpm logic
```

**Refactoring Recommendation:**

```python
@dataclass
class RateLimiter:
    max_rps: int
    max_rpm: int
    recent: Deque[float] = field(default_factory=lambda: deque(maxlen=10000))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allow(self) -> bool:
        async with self.lock:
            return self._check_and_record(time.time())
    
    def _check_and_record(self, now: float) -> bool:
        # Common implementation
        ...

@dataclass
class KeyedRateLimiter:
    max_rps: int
    max_rpm: int
    limiter_factory: Callable[[], RateLimiter] = field(
        default_factory=lambda: lambda: RateLimiter(0, 0)
    )
    limiters: dict[str, RateLimiter] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allow(self, key: str) -> bool:
        async with self.lock:
            if key not in self.limiters:
                self.limiters[key] = RateLimiter(self.max_rps, self.max_rpm)
            return await self.limiters[key].allow()
```

---

### 3. `health.py`: `get_health_map()` and `get_accounts_health()` - **Exact duplication of ~30 lines**

**Problem:** Two functions share identical health calculation logic (lines 344-376 and 379-413).

**Refactoring Recommendation:**

```python
# BEFORE: Duplicated logic
def get_health_map(config, registry, state):
    for key in registry.keys:
        usage = fetch_usage(...)
        key_state = state.keys.get(key.label, KeyState())
        total = max(key_state.request_count, 1)
        error_rate = (key_state.error_403 + key_state.error_429 + key_state.error_5xx) / total
        blocked = is_blocked(state, key.label)
        status = score_key(usage, key_state, is_exhausted(state, key.label), blocked)
        health[key.label] = HealthInfo(...)

def get_accounts_health(config, accounts, state, force_real=False):
    for account in accounts:
        usage = fetch_usage(...)
        key_state = state.keys.get(account.label, KeyState())
        total = max(key_state.request_count, 1)
        error_rate = (key_state.error_403 + key_state.error_429 + key_state.error_5xx) / total
        # ... identical calculation

# AFTER: Extract common builder
def _build_health_info(label: str, api_key: str, base_url: str, 
                       state: State, config: Config, force_real: bool = False) -> HealthInfo:
    usage = fetch_usage(base_url, api_key, dry_run=...)
    key_state = state.keys.get(label, KeyState())
    total = max(key_state.request_count, 1)
    error_rate = (key_state.error_403 + key_state.error_429 + key_state.error_5xx) / total
    blocked = is_blocked(state, label)
    status = score_key(usage, key_state, is_exhausted(state, label), blocked)
    return HealthInfo(...)

def get_health_map(config, registry, state):
    return {
        key.label: _build_health_info(key.label, key.api_key, 
                                      config.upstream_base_url, state, config)
        for key in registry.keys
    }
```

---

### 4. `ui.py`: `render_accounts_health_dashboard()` - **238 lines, 7-level nesting**

**Problem:** This function (lines 603-904) handles:
- Account filtering and aliasing
- Signature-based deduplication
- Email resolution
- Row building and display computation
- Complex conditional panel rendering

The nested `row_reset_seconds` function (lines 717-728) is defined inside a loop and duplicates `_reset_seconds()` logic.

**Refactoring Recommendation:**

```python
def render_accounts_health_dashboard(...):
    # Extract: Build row data
    rows = _build_account_rows(accounts, state, health, aliases, email_by_label)
    
    # Extract: Apply display transformations
    next_candidate = _find_next_candidate(rows)
    _apply_display_properties(rows, next_candidate)
    
    # Extract: Sort and render
    _render_sorted_rows(rows, console)

# Separate module: ui_renderers.py
def _render_account_panel(row: dict, console: Console) -> None:
    lines = _build_account_panel_lines(row)  # Extract line building
    body = Text("\n").join(lines)
    console.print(Panel(body, title=..., border_style=...))
```

---

### 5. `cli.py`: `_run_e2e()` function - **Cyclomatic Complexity: 20+**

**Problem:** This function (lines 948-1063) mixes:
- Configuration validation
- Proxy process management
- HTTP request batching
- Statistics tracking
- Cleanup handling

The nested try-finally with subprocess management makes error handling brittle.

---

### 6. `rotation.py`: `_build_stay_reason()` - **Cognitive Complexity: High**

**Problem:** Function (lines 164-239) has multiple deeply nested conditionals building human-readable strings:

```python
def _build_stay_reason(...):
    if current_score == runner_score:
        if cur_remaining is not None:
            return f"..."
        return f"..."
    if cur_remaining is not None and runner_remaining is not None:
        return f"..."
    if (... and current_info.error_rate != runner_info.error_rate):
        return f"..."
    # ... more conditions
```

**Refactoring Recommendation:**

```python
def _build_stay_reason(key, current_idx, candidates, health):
    if not candidates:
        return None
    
    runner = _find_runner_up(candidates, current_idx)
    if not runner:
        return None
    
    comparison = _compare_keys(health.get(key.label), runner[2])
    return _format_stay_reason(comparison, key.label, runner[1].label)

@dataclass
class KeyComparison:
    reason_type: str  # "tie", "quota", "error_rate", "status", "default"
    current_value: Any
    runner_value: Any

def _format_stay_reason(comp: KeyComparison, current_label: str, runner_label: str) -> str:
    formatters = {
        "tie": lambda c: f"Current key ties for best...",
        "quota": lambda c: f"Current key has higher remaining quota...",
        # ...
    }
    return formatters.get(comp.reason_type, lambda c: None)(comp)
```

---

### 7. `auth_accounts.py`: Multiple `_extract_email_from_*` functions - **Pattern repetition**

**Problem:** Five functions (`_extract_email_from_values`, `_extract_email_from_config`, `_extract_email_from_text`, plus inline extraction in `_account_from_env`, `_account_from_json`) all search for email patterns with subtle differences.

---

### 8. `config.py` & `keys.py`: Duplicate `_parse_bool()` functions

**Problem:** Identical logic in both files:

```python
# config.py line 73-77
def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    value = value.strip().lower()
    return value in {"1", "true", "yes", "on"}

# keys.py line 44-47
def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
```

**Recommendation:** Move to a shared `utils.py` or `parsing.py` module.

---

## 🟡 Medium-Priority Issues

### 9. `proxy.py`: Magic numbers and string constants

**Lines 82-107:** Payment error tokens are inline constants:

```python
_PAYMENT_ERROR_TOKENS = (
    "payment", "payment_required", "natpament", ...
    "\u4f59\u989d\u4e0d\u8db3",  # Chinese characters
    ...
)
```

**Recommendation:** Extract to a configuration file or at least add structure:

```python
@dataclass(frozen=True)
class PaymentErrorPatterns:
    english: tuple[str, ...] = ("payment", "billing", ...)
    chinese: tuple[str, ...] = ("...", ...)
    
    def __iter__(self):
        return iter(self.english + self.chinese)
```

---

### 10. `ui.py`: Multiple functions over 50 lines without clear separation

- `_format_reset_hint()` (lines 234-256): 22 lines, mixes parsing logic
- `_limit_display()` (lines 418-428): Could be simplified
- `render_health_dashboard()` (lines 294-415): Complex row building

---

### 11. `cli.py`: `_render_status()` - **Mixed abstraction levels**

Lines 366-498 mix:
- Data building (`_build_status_payload`)
- Rich UI formatting
- Conditional alert generation

The function builds panels inline rather than delegating to specialized renderers.

---

### 12. `health.py`: `_extract_remaining_percent()` - **Deep nesting, multiple return paths**

Lines 72-95 have 4 levels of nesting and 6 return statements, making the flow hard to follow.

---

### 13. `auth_accounts.py`: `load_accounts_from_auths_dir()` - **Long conditional chain**

Lines 303-323 use a long if-elif chain for file type dispatch that could use a registry pattern:

```python
# BEFORE
if path.suffix.lower() == ".env":
    account = _account_from_env(...)
elif path.suffix.lower() == ".toml":
    account = _account_from_toml(...)
# ...

# AFTER
_ACCOUNT_PARSERS: dict[str, Callable] = {
    ".env": _account_from_env,
    ".toml": _account_from_toml,
    ".json": _account_from_json,
    ".bak": _account_from_json,
}
```

---

### 14. `rotation.py`: `select_key_round_robin()` - **Two similar loops**

Lines 320-355 have nearly identical logic repeated for "with health" and "without health" cases.

---

### 15. `trace.py` & `cli.py`: Duplicate `_tail_lines` logic

Both modules implement file tailing with slightly different approaches.

---

### 16-20. Naming inconsistencies

| Issue | Location | Current | Suggested |
|-------|----------|---------|-----------|
| Abbreviation | `health.py:36` | `Usage` | `QuotaUsage` |
| Ambiguous | `rotation.py:69` | `next_healthy_index` | `find_next_healthy_index` |
| Inconsistent prefix | `ui.py` | `_format_*`, `_build_*` | Standardize on one verb |
| Typo in constant | `proxy.py:85` | `"natpament"` | `"notpayment"` (verify) |
| Unclear | `rotation.py:108` | `_manual_score` | `_calculate_resource_score` |

---

## Complexity Scores Summary

| Function | File | Lines | Cyclomatic Complexity | Grade |
|----------|------|-------|----------------------|-------|
| `proxy` (nested) | proxy.py | 237 | 35+ | 🔴 F |
| `render_accounts_health_dashboard` | ui.py | 301 | 25+ | 🔴 F |
| `_run_e2e` | cli.py | 115 | 20+ | 🔴 D |
| `create_app` | proxy.py | 287 | 18 | 🟡 C |
| `rotate_manual` | rotation.py | 68 | 15 | 🟡 C |
| `_build_stay_reason` | rotation.py | 75 | 14 | 🟡 C |
| `fetch_usage` | health.py | 78 | 12 | 🟡 C |
| `_render_status` | cli.py | 132 | 12 | 🟡 C |
| `_account_from_toml` | auth_accounts.py | 33 | 10 | 🟢 B |
| `load_state` | state.py | 64 | 9 | 🟢 B |

---

## Refactoring Roadmap

### Phase 1: Critical (Immediate)
1. Extract `proxy` function into handler classes
2. Deduplicate rate limiters
3. Merge health calculation functions

### Phase 2: High (Next Sprint)
4. Refactor `render_accounts_health_dashboard`
5. Simplify `_run_e2e`
6. Extract shared parsing utilities

### Phase 3: Medium (Backlog)
7. Standardize naming conventions
8. Extract constants to configuration
9. Add registry pattern for file parsers

---

## Positive Findings

Despite the issues, the codebase shows good practices:

✅ **Excellent module documentation** - Every module has comprehensive docstrings  
✅ **Type hints throughout** - Strong typing helps catch errors early  
✅ **Dataclass usage** - Proper use of `@dataclass` for data containers  
✅ **Async/await patterns** - Modern Python async usage  
✅ **State management** - Clean separation with State/KeyState  
✅ **File locking** - Proper `locking.py` module for concurrency  
✅ **Configuration pattern** - Immutable frozen Config dataclass  

---

## Verdict

**Grade: B**

The KMI Manager CLI codebase has a solid architectural foundation with clear module boundaries and good use of modern Python features. However, the complexity is concentrated in a few "hot spots" - particularly `proxy.py` and `ui.py` - where functions have grown beyond maintainable sizes.

**Priority Actions:**
1. Break down the 237-line `proxy` function immediately
2. Extract shared rate limiting and health calculation logic
3. Add complexity linting (e.g., `radon`, `xenon`) to CI to prevent regression

The codebase is **maintainable with refactoring** - the issues are structural rather than architectural, making them addressable without major rewrites.

---

*Generated by: Maintainability Anti-Entropy Agent*  
*Methodology: Cyclomatic complexity analysis, DRY violation detection, SRP assessment*
