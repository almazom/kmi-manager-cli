# 🏛️ Architectural Review: KMI Manager CLI

**Reviewer:** Rafael, Architecture Guardian  
**Date:** 2026-02-04  
**Protocol:** NASA-Boeing Pegasus-5  
**Mother's Verdict:** "Good bones, but needs a stronger foundation"

---

## Executive Summary

The KMI Manager CLI exhibits a **three-layer architecture** that is conceptually sound but suffers from **implementation-level violations** of SOLID principles, primarily in the proxy layer. The domain model is well-designed, but service boundaries are bleeding into each other.

**Overall Grade:** B- (Good structure, needs refactoring for maintainability)

---

## 1. 🌳 Trunk-Branch-Leaf Analysis

### 🪵 TRUNK - Core Domain Logic (Protect at All Costs)

| Module | Responsibility | Stability |
|--------|---------------|-----------|
| `rotation.py` | Key selection algorithms (manual, round-robin) | ⭐⭐⭐ HIGH |
| `state.py` | State persistence, schema versioning | ⭐⭐⭐ HIGH |
| `keys.py` | Key registry, key metadata | ⭐⭐⭐ HIGH |
| `health.py` | Health scoring, usage parsing | ⭐⭐⭐ HIGH |

**Characteristics:**
- Pure business logic with no I/O (except state.py's persistence)
- Well-defined data structures (dataclasses)
- Deterministic algorithms
- **These must never import from UI, CLI, or Proxy layers**

### 🌿 BRANCH - Service Boundaries & Contracts

| Module | Responsibility | Stability |
|--------|---------------|-----------|
| `config.py` | Configuration loading, validation | ⭐⭐ MEDIUM |
| `proxy.py` | HTTP proxy service (FastAPI) | ⭐ LOW |
| `cli.py` | Command-line interface | ⭐ LOW |
| `locking.py` | File locking primitives | ⭐⭐ MEDIUM |

**Characteristics:**
- Define contracts between layers
- Handle I/O and external dependencies
- Subject to frequent change based on requirements

### 🍃 LEAF - Implementation Details (Change Freely)

| Module | Responsibility | Stability |
|--------|---------------|-----------|
| `ui.py` | Rich terminal rendering | ⭐ LOW |
| `trace_tui.py` | Trace viewer TUI | ⭐ LOW |
| `logging.py` | Structured logging setup | ⭐ LOW |
| `security.py` | File permission hardening | ⭐⭐ MEDIUM |
| `doctor.py` | Diagnostics | ⭐ LOW |
| `errors.py` | Error messages | ⭐ LOW |
| `time_utils.py` | Timezone utilities | ⭐⭐ MEDIUM |

**Characteristics:**
- Presentational concerns
- Utility functions
- Can be refactored without domain impact

---

## 2. 🔴 Critical Architectural Violations

### VIOLATION-001: God Object in `proxy.py` (SEVERITY: CRITICAL)

**WHAT:** The `proxy.py` module (907 lines) violates Single Responsibility Principle.

**Current Contents:**
- HTTP request handling (FastAPI route)
- Rate limiting (RateLimiter, KeyedRateLimiter)
- State persistence (StateWriter)
- Trace logging (TraceWriter)
- Health refresh background loops
- Error detection and parsing
- Payment error detection

**Impact:**
- **Story Points to Modify:** 8+ (any change requires understanding 900+ lines)
- **Test Complexity:** High - requires mocking HTTP, async, and state
- **Cyclomatic Complexity:** Estimated 35+ (too high for a single module)

**Pegasus-5 Analysis:**
```
WHAT:      HTTP proxy service with rate limiting and state management
SUCCESS:   Handle 1000+ concurrent requests, <50ms latency overhead
CONSTRAINTS: Must not lose state on crash, must debounce writes
TESTS:     Integration tests, load tests, chaos tests
```

**Recommendation (ADR-001):**
```python
# EXTRACT: proxy/limiters.py
class RateLimiter: ...
class KeyedRateLimiter: ...

# EXTRACT: proxy/writers.py  
class StateWriter: ...
class TraceWriter: ...

# EXTRACT: proxy/health_loop.py
async def _health_refresh_loop(ctx): ...

# KEEP: proxy.py (reduced to ~300 lines)
# - create_app()
# - ProxyContext (reduced)
# - Request handler route
```

**Complexity Reduction:** 907 → ~300 lines (66% reduction)

---

### VIOLATION-002: Circular Dependency Between Health and Rotation (SEVERITY: HIGH)

**WHAT:** `health.py` imports from `rotation.py`, and `rotation.py` depends on `HealthInfo`.

```python
# health.py
from kmi_manager_cli.rotation import is_blocked, is_exhausted  # LINE 13

# rotation.py  
if TYPE_CHECKING:
    from kmi_manager_cli.health import HealthInfo  # LINE 8-9
```

**Impact:**
- Architectural boundary violation
- Makes independent testing difficult
- Prevents separate deployment of these domains

**Pegasus-5 Analysis:**
```
WHAT:      Health scoring needs blocked/exhausted status
SUCCESS:   Accurate health status for all keys
CONSTRAINTS: Must not depend on rotation logic
TESTS:     Unit tests for each module independently
```

**Recommendation (ADR-002):**

Option A - **Extract Status Module** (Preferred):
```python
# NEW: key_status.py
@dataclass
class KeyStatus:
    blocked_until: Optional[datetime]
    exhausted_until: Optional[datetime]
    
def is_blocked(status: KeyStatus) -> bool: ...
def is_exhausted(status: KeyStatus) -> bool: ...
```

Option B - **Dependency Inversion**:
```python
# rotation.py accepts status checkers as parameters
def select_key_round_robin(
    registry, state, health,
    is_blocked_fn: Callable[[State, str], bool],
    is_exhausted_fn: Callable[[State, str], bool],
): ...
```

---

### VIOLATION-003: ProxyContext is a Blob (SEVERITY: HIGH)

**WHAT:** `ProxyContext` has 13 fields, indicating high coupling.

```python
@dataclass
class ProxyContext:
    config: Config                    # Configuration
    registry: Registry                # Key registry
    state: State                      # Mutable state
    rate_limiter: "RateLimiter"       # Rate limiting
    key_rate_limiter: "KeyedRateLimiter"  # Per-key limiting
    state_lock: asyncio.Lock          # Concurrency control
    state_writer: "StateWriter"       # Persistence
    trace_writer: "TraceWriter"       # Logging
    http_client: Optional[httpx.AsyncClient]  # HTTP
    health_cache: dict[str, "HealthInfo"]     # Cached health
    health_cache_ts: float            # Cache timestamp
    blocklist_recheck_ts: float       # Recheck timing
    health_stop: asyncio.Event        # Lifecycle
    health_task: Optional[asyncio.Task]       # Background task
```

**Impact:**
- Any change requires modifying the entire context
- Testing requires mocking all 13 dependencies
- Violates Interface Segregation Principle

**Recommendation (ADR-003):**

Split into cohesive sub-contexts:
```python
@dataclass
class ProxyContext:
    config: Config
    deps: ProxyDependencies  # Grouped dependencies
    lifecycle: ProxyLifecycle  # Health task, stop events

@dataclass  
class ProxyDependencies:
    registry: Registry
    state_manager: StateManager  # Combines state + lock + writer
    rate_limiters: RateLimiters  # Combines both limiters
    http_client: httpx.AsyncClient
    trace_writer: TraceWriter
```

---

### VIOLATION-004: Mixed Sync/Async Architecture Without Clear Boundaries (SEVERITY: MEDIUM)

**WHAT:** Health fetching uses `asyncio.to_thread()` to wrap sync code.

```python
# proxy.py line 306-308
health = await asyncio.to_thread(
    get_health_map, ctx.config, ctx.registry, ctx.state
)
```

**Impact:**
- Thread pool exhaustion risk under load
- Harder to reason about concurrency
- Error handling complexity (sync vs async exceptions)

**Pegasus-5 Analysis:**
```
WHAT:      Fetch health data from upstream API
SUCCESS:   Non-blocking health refresh every N seconds
CONSTRAINTS: Must not block event loop
TESTS:     Concurrent health fetch under load
```

**Recommendation (ADR-004):**

Create async-native health client:
```python
# health_async.py
class AsyncHealthClient:
    async def fetch_usage(self, ...) -> Optional[Usage]: ...
    async def get_health_map(self, ...) -> dict[str, HealthInfo]: ...
```

Or use `httpx.AsyncClient` consistently throughout.

---

## 3. 🟡 Areas Needing Boundary Protection

### AREA-001: State-Registry Coupling

**Current State:**
```python
# state.py line 106
def load_state(config: Config, registry: Registry) -> State:
    # Registry required to initialize state.keys
```

**Concern:** Loading state requires registry - temporal coupling.

**Protection:** Define clear initialization contract:
```python
@dataclass
class InitializedState:
    """State that has been synced with a registry."""
    state: State
    registry: Registry  # Immutable reference
```

---

### AREA-002: Config Proliferation

**Current State:** `Config` has 35+ fields.

**Concern:** Config acts as a global dependency, making testing difficult.

**Protection:** Group related config into sub-configs:
```python
@dataclass(frozen=True)
class Config:
    proxy: ProxyConfig      # 8 fields
    rotation: RotationConfig  # 5 fields  
    logging: LoggingConfig  # 4 fields
    # ... etc
```

---

### AREA-003: Error Handling Strategy

**Current State:** Multiple error handling patterns:
- `remediation_message()` for user-facing errors
- `log_event()` for structured logging
- Direct `typer.echo()` in CLI
- Exception raising in proxy

**Protection:** Define error taxonomy:
```python
class KMIError(Exception): ...
class KeyExhaustedError(KMIError): ...
class RotationError(KMIError): ...
class ProxyError(KMIError): ...

# Single error handler
def handle_error(error: KMIError, context: ErrorContext) -> Response:
    # Centralized logging, user messaging, metrics
```

---

## 4. 📋 ADR-Style Recommendations

### ADR-005: Extract Rate Limiting to Dedicated Module

**Status:** Proposed  
**Complexity:** 3 story points  
**Risk:** Low

```
Context:    Rate limiting is embedded in proxy.py
Decision:   Extract to rate_limiting.py module
Consequences:
    + Independent testing of rate limiting
    + Reusable for other services
    + Reduces proxy.py complexity
    - Additional module to maintain
```

### ADR-006: Implement Repository Pattern for State

**Status:** Proposed  
**Complexity:** 5 story points  
**Risk:** Medium

```
Context:    State persistence is coupled to file system
Decision:   Create StateRepository abstraction

interface StateRepository:
    load() -> State
    save(state: State) -> None
    
class FileStateRepository(StateRepository): ...
class MemoryStateRepository(StateRepository): ...  # For testing

Consequences:
    + Testability improves dramatically
    + Could support Redis/distributed state later
    - Adds abstraction overhead
```

### ADR-007: Create Proxy Middleware Pipeline

**Status:** Proposed  
**Complexity:** 8 story points  
**Risk:** Medium

```
Context:    Proxy request handling is monolithic
Decision:   Implement middleware pattern

middleware_chain = [
    AuthMiddleware(),      # _authorize_request
    RateLimitMiddleware(), # Global rate limiting
    KeySelectMiddleware(), # _select_key
    KeyRateLimitMiddleware(), # Per-key limiting
    UpstreamMiddleware(),  # HTTP request
    ErrorDetectMiddleware(), # Payment error detection
]

Consequences:
    + Each middleware independently testable
    + Can reorder/disable middleware via config
    + Clear request lifecycle
    - More complex to trace execution
```

---

## 5. 📊 Complexity Assessment

### Module Complexity Matrix

| Module | Lines | Cyclomatic | Story Points | Risk Level |
|--------|-------|------------|--------------|------------|
| proxy.py | 907 | 35+ | 13 | 🔴 HIGH |
| cli.py | 1000+ | 40+ | 13 | 🔴 HIGH |
| health.py | 413 | 25 | 8 | 🟡 MEDIUM |
| rotation.py | 464 | 20 | 8 | 🟡 MEDIUM |
| state.py | 208 | 12 | 5 | 🟢 LOW |
| keys.py | 142 | 8 | 3 | 🟢 LOW |
| config.py | 326 | 15 | 5 | 🟢 LOW |

### Change Impact Analysis

**If you need to modify:**

| Change | Affected Modules | Risk | Estimated Effort |
|--------|-----------------|------|------------------|
| Add new rotation algorithm | rotation.py | Low | 3 SP |
| Add new health metric | health.py, rotation.py | Medium | 5 SP |
| Modify rate limiting | proxy.py | High | 8 SP |
| Add proxy auth method | proxy.py | High | 8 SP |
| Change state schema | state.py | Medium | 5 SP |
| Add CLI command | cli.py | Low | 3 SP |

---

## 6. 🏛️ Architectural Boundaries Map

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ cli.py   │  │ ui.py    │  │trace_tui │  │doctor.py │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼─────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ proxy.py     │  │ health.py    │  │ logging.py   │      │
│  │ (REFACTOR)   │  │              │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘      │
│         │                 │                                 │
│         ▼                 ▼                                 │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ rate_limiting│  │ config.py    │  ◄─── External I/O     │
│  │ (EXTRACT)    │  │ (refactor)   │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────┬─────────────────┬─────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                     DOMAIN LAYER                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │rotation.py│  │ state.py │  │ keys.py  │  │key_status│   │
│  │          │  │          │  │          │  │(EXTRACT) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
│  🔒 NEVER IMPORT FROM UPPER LAYERS                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 🍷 Mom-Approved Recommendations

### Immediate Actions (This Sprint)

1. **Extract Rate Limiters** (3 SP)
   - Move `RateLimiter` and `KeyedRateLimiter` to `rate_limiting.py`
   - Reduces `proxy.py` by ~80 lines

2. **Extract Writers** (3 SP)
   - Move `StateWriter` and `TraceWriter` to `persistence.py`
   - Reduces `proxy.py` by ~100 lines

3. **Fix Circular Dependency** (2 SP)
   - Move `is_blocked`, `is_exhausted` to new `key_status.py` module
   - Both `health.py` and `rotation.py` import from `key_status.py`

### Short-term (Next 2 Sprints)

4. **ProxyContext Refactoring** (5 SP)
   - Group related dependencies into sub-contexts
   - Improves testability

5. **Add Async Health Client** (3 SP)
   - Create `health_async.py` with native async support
   - Remove `asyncio.to_thread()` wrappers

### Long-term (Next Quarter)

6. **Repository Pattern** (5 SP)
   - Abstract state persistence
   - Enables testing without file system

7. **Middleware Pipeline** (8 SP)
   - Refactor proxy into composable middleware
   - Dramatically improves maintainability

---

## 8. 🎯 Architectural Verdict

### Strengths ✅

1. **Clean Domain Model**: `KeyRecord`, `KeyState`, `HealthInfo`, `Usage` are well-designed
2. **Schema Versioning**: State migration logic shows foresight
3. **Async Safety**: Proper use of locks and debounced writes
4. **Configuration Design**: Frozen dataclass with validation
5. **Separation of Concerns**: CLI, Proxy, and Domain are conceptually separate

### Weaknesses ⚠️

1. **God Object**: `proxy.py` is too large and does too much
2. **Circular Dependencies**: Health ↔ Rotation coupling
3. **Mixed Sync/Async**: `asyncio.to_thread()` is a code smell
4. **High Coupling**: `ProxyContext` has too many dependencies
5. **Config Proliferation**: 35+ fields in Config dataclass

### Overall Assessment

**Grade: B-**

The architecture has a **solid foundation** but needs **refactoring to reduce coupling** in the proxy layer. The domain logic (rotation, health, state) is well-designed and should be protected. The proxy layer needs immediate attention to prevent it from becoming unmaintainable.

**Risk Assessment:**
- Current risk: MEDIUM (changes to proxy are error-prone)
- Risk after refactoring: LOW (clear boundaries, testable components)

**Mother Says:**
> "The wine is good, but it needs to breathe. Let the architecture breathe by extracting those classes. And remember: a function should do one thing, just like I make one meal at a time."

---

## Appendix: SOLID Compliance Matrix

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **S**ingle Responsibility | ⚠️ Partial | proxy.py and cli.py violations |
| **O**pen/Closed | ✅ Good | Extension via config flags |
| **L**iskov Substitution | ✅ Good | Dataclass hierarchies are simple |
| **I**nterface Segregation | ⚠️ Partial | ProxyContext too large |
| **D**ependency Inversion | ⚠️ Partial | Direct imports vs interfaces |

---

*"Architecture is the art of making complex things simple. This codebase is halfway there."*  
— Rafael, after his third glass of wine 🍷
