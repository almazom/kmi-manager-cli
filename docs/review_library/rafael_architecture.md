# KMI Manager CLI - Architecture Review

**Reviewer:** Rafael, Architecture Guardian  
**Date:** 2026-02-02  
**Protocol:** NASA-Boeing Pegasus-5  
**Project:** KMI Manager CLI v0.1.0  

---

## Executive Summary

The KMI Manager CLI is a Python-based command-line tool for API key rotation, proxy server management, and health monitoring for Kimi CLI multi-account configurations. This review applies architectural governance principles derived from Martin Fowler, Robert C. Martin (Uncle Bob), and Eric Evans.

**Overall Assessment:** ⚠️ **YELLOW** - Functional architecture with acceptable technical debt. Some areas require attention before major feature additions.

---

## 1. Trunk-Branch-Leaf Analysis

### 1.1 TRUNK - Core Domain Logic

The trunk contains modules that define the fundamental domain model and state management. Changes here ripple throughout the system.

| Module | Lines | Responsibility | Stability |
|--------|-------|----------------|-----------|
| `config.py` | 294 | Configuration domain model, env parsing, validation | HIGH |
| `state.py` | 185 | State persistence, KeyState/State dataclasses | HIGH |
| `keys.py` | 116 | KeyRecord/Registry domain models | HIGH |
| `errors.py` | 33 | Error message catalog | MEDIUM |

**Key Observations:**
- **Config** uses a frozen dataclass pattern (immutable) - excellent for thread safety
- **State** implements schema versioning with migration - good for backward compatibility
- **Keys** uses `__post_init__` for hash computation - appropriate for domain logic
- Circular dependency risk: `state.py` → `keys.py` → `auth_accounts.py` → `config.py` (acceptable, no cycles detected)

### 1.2 BRANCHES - Service Modules

Service modules implement use cases and orchestrate domain logic.

| Module | Lines | Responsibility | Coupling |
|--------|-------|----------------|----------|
| `rotation.py` | 406 | Key selection algorithms, eligibility logic | MEDIUM |
| `health.py` | 412 | Health monitoring, usage fetching | MEDIUM |
| `proxy.py` | 887 | FastAPI proxy server, rate limiting | HIGH |
| `auth_accounts.py` | 350 | Account loading from multiple formats | MEDIUM |

**Key Observations:**
- **rotation.py**: Clean separation of manual vs auto-rotation strategies. Score-based selection is well-designed.
- **health.py**: Heavy JSON parsing logic (200+ lines) could be extracted to a parser submodule
- **proxy.py**: Large module violating Single Responsibility. Contains rate limiting, auth, routing, and error handling.
- **auth_accounts.py**: Good support for multiple formats (.env, .toml, .json) with provider selection logic

### 1.3 LEAVES - UI and Utilities

Leaf modules have high churn and low coupling to domain logic.

| Module | Lines | Responsibility | Churn Risk |
|--------|-------|----------------|------------|
| `ui.py` | 824 | Rich console rendering, dashboards | HIGH |
| `trace_tui.py` | ~200 | Interactive trace TUI (estimated) | HIGH |
| `cli.py` | 1000+ | Typer command definitions | HIGH |
| `doctor.py` | 335 | Diagnostics and health checks | MEDIUM |
| `trace.py` | 145 | Trace logging and rotation | MEDIUM |
| `logging.py` | 69 | JSON logger configuration | LOW |
| `security.py` | 59 | File permission checks | LOW |
| `locking.py` | 53 | File locking primitives | LOW |
| `time_utils.py` | ~50 | Timezone handling (estimated) | LOW |
| `audit.py` | 17 | Audit event logging | LOW |

**Key Observations:**
- **ui.py** is the largest leaf module - extensive Rich formatting logic
- **cli.py** exceeds 1000 lines - command definitions should be split into submodules
- Utility modules are appropriately sized and focused

---

## 2. PEGASUS-5 Gates Analysis

### 2.1 GATE 1: WHAT - Architectural Requirements

#### Clear Requirements
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Multi-account API key support | ✅ | `auth_accounts.py`, `keys.py` |
| Automatic key rotation | ✅ | `rotation.py` - round-robin and health-based |
| Proxy server with rate limiting | ✅ | `proxy.py` - RateLimiter, KeyedRateLimiter |
| Health monitoring | ✅ | `health.py` - usage fetching, scoring |
| Secure state management | ✅ | `state.py`, `locking.py`, `security.py` |
| Audit logging | ✅ | `audit.py`, `logging.py` |
| Multi-format config support | ✅ | `.env`, `.toml`, `.json` in `auth_accounts.py` |

#### Ambiguous Requirements
| Area | Concern | Risk |
|------|---------|------|
| "E2E testing" in auto-rotation | Implicit dependency on external API | HIGH |
| Trace retention policy | Configurable but no purge strategy | MEDIUM |
| Blocklist recheck semantics | Time-based vs event-based unclear | MEDIUM |

**BLOCKING SPECIFICATION GAPS:**
1. No documented SLA for proxy request latency
2. No explicit consistency model for distributed state
3. Unclear behavior when all keys exhausted

### 2.2 GATE 2: SUCCESS - Measurable Criteria

| Criterion | Target | Current | Status |
|-----------|--------|---------|--------|
| Test Coverage | >90% | 95% (per pyproject.toml) | ✅ PASS |
| Module Size | <500 lines | 3 modules exceed | ⚠️ WARN |
| Cyclomatic Complexity | <10 per function | TBD | ⚠️ REVIEW |
| Public API Surface | Documented | Undocumented | ❌ FAIL |
| Configuration Validation | All inputs | Partial | ⚠️ WARN |

### 2.3 GATE 3: CONSTRAINTS - Boundaries and Limitations

#### Hard Constraints (Cannot Change)
| Constraint | Impact |
|------------|--------|
| Python 3.9+ compatibility | Limits type hint syntax |
| File-based state storage | No horizontal scaling |
| Single-process proxy | Throughput limited |
| POSIX/Windows file locking | Platform-specific behavior |

#### Soft Constraints (Change with Caution)
| Constraint | Impact |
|------------|--------|
| Typer CLI framework | Migration cost high |
| FastAPI for proxy | Performance vs flexibility tradeoff |
| Rich for UI | Terminal compatibility issues |
| httpx for HTTP | Dependency lock-in |

#### Architectural Boundaries
```
┌─────────────────────────────────────────────────────────────┐
│  CLI Layer (cli.py) - Typer commands                         │
├─────────────────────────────────────────────────────────────┤
│  Service Layer (proxy.py, rotation.py, health.py)           │
├─────────────────────────────────────────────────────────────┤
│  Domain Layer (config.py, state.py, keys.py)                │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure (locking.py, security.py, logging.py)        │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 GATE 4: TESTS - Verification Strategy

| Test Category | Coverage | Gaps |
|---------------|----------|------|
| Unit tests | Extensive (36 test files) | Some mocking of external APIs |
| Integration tests | Partial | Proxy async testing limited |
| E2E tests | Implicit in auto-rotation | Depends on live API |
| Security tests | File permissions only | No penetration testing |
| Performance tests | None | Rate limiting not load-tested |

**Coverage Exclusions (pyproject.toml):**
- `cli.py` - excluded (UI logic)
- `ui.py` - excluded (presentation)
- `trace_tui.py` - excluded (interactive)

**Recommendation:** Consider adding property-based testing for rotation algorithms.

---

## 3. SOLID Compliance Assessment

### 3.1 Single Responsibility Principle (SRP)

| Module | Responsibilities | Grade |
|--------|-----------------|-------|
| `proxy.py` | Rate limiting, auth, routing, retries, error handling, streaming | C |
| `rotation.py` | Manual rotation, auto-rotation, eligibility, scoring | B |
| `health.py` | Usage fetching, parsing, scoring, health mapping | C |
| `cli.py` | Commands, daemon control, log tailing, E2E testing | D |
| `ui.py` | Tables, panels, formatting, i18n (Russian) | B |

**Violations:**
- `proxy.py` violates SRP - should split into: `proxy_server.py`, `rate_limiter.py`, `proxy_auth.py`
- `cli.py` violates SRP - command groups should be separate modules

### 3.2 Open/Closed Principle (OCP)

| Extension Point | Status | Notes |
|-----------------|--------|-------|
| New auth formats | ✅ Open | `auth_accounts.py` pattern matching |
| New rotation strategies | ⚠️ Partial | Hardcoded in `rotation.py` |
| New health checks | ⚠️ Partial | `score_key` function |
| New UI themes | ❌ Closed | Hardcoded styles |

**Recommendation:** Introduce strategy pattern for rotation algorithms.

### 3.3 Liskov Substitution Principle (LSP)

Dataclasses are used consistently. No inheritance hierarchy issues detected.

### 3.4 Interface Segregation Principle (ISP)

| Interface | Consumers | Assessment |
|-----------|-----------|------------|
| `Config` | All modules | Well-defined, frozen |
| `State` | rotation, proxy, cli | Appropriate surface |
| `KeyRecord` | keys, rotation, proxy | Minimal and focused |

### 3.5 Dependency Inversion Principle (DIP)

| Dependency | Direction | Assessment |
|------------|-----------|------------|
| Domain → Infrastructure | ❌ Violation | `state.py` imports `locking.py` |
| Services → Domain | ✅ Correct | Clean dependency |
| CLI → Services | ✅ Correct | Appropriate coupling |

**Recommendation:** Consider introducing repository pattern for state persistence.

---

## 4. Architectural Patterns Identified

### 4.1 Implemented Patterns

| Pattern | Location | Implementation Quality |
|---------|----------|----------------------|
| **Repository** | `state.py`, `keys.py` | Simple but effective |
| **Strategy** | `rotation.py` (implicit) | Could be explicit |
| **Circuit Breaker** | `rotation.py` (block/exhaust) | Good implementation |
| **Token Bucket** | `proxy.py` RateLimiter | Correct implementation |
| **Debounced Writer** | `proxy.py` StateWriter | Async pattern well-done |
| **CQRS** (partial) | Trace vs State | Separate read/write paths |

### 4.2 Missing Patterns (Recommendations)

| Pattern | Benefit | Priority |
|---------|---------|----------|
| Factory | Account creation from multiple formats | Medium |
| Observer | State change notifications | Low |
| Chain of Responsibility | Request middleware in proxy | Medium |
| Adapter | Abstract external API differences | Low |

---

## 5. Complexity Assessment

### 5.1 Module Complexity (Story Points)

| Module | Points | Rationale |
|--------|--------|-----------|
| `proxy.py` | 13 | Async, rate limiting, streaming, retries |
| `cli.py` | 13 | Multiple commands, daemon management, E2E |
| `ui.py` | 8 | Rich formatting, i18n, dashboard logic |
| `rotation.py` | 8 | Scoring algorithms, tie-breaking |
| `health.py` | 8 | JSON parsing, multiple formats |
| `auth_accounts.py` | 8 | Multi-format parsing, provider selection |
| `config.py` | 5 | Validation, defaults, env loading |
| `state.py` | 5 | Persistence, migration, locking |
| `doctor.py` | 5 | Diagnostics, permission checks |
| `trace.py` | 5 | Rotation, JSONL handling |
| Others | 2-3 each | Utilities |

**Total Estimated:** ~90 story points

### 5.2 Cyclomatic Complexity Hotspots

| Function | Module | Complexity | Risk |
|----------|--------|------------|------|
| `proxy()` | `proxy.py` | High | Request handling logic |
| `_run_e2e()` | `cli.py` | High | Test orchestration |
| `render_accounts_health_dashboard()` | `ui.py` | High | Display logic |
| `rotate_manual()` | `rotation.py` | Medium | Tie-breaking logic |
| `score_key()` | `health.py` | Medium | Status determination |

---

## 6. Agent-Safe Boundaries

### 6.1 SAFE ZONES - Agents Can Modify

These modules have clear interfaces and low coupling:

| Module | Safe Operations |
|--------|-----------------|
| `errors.py` | Add new error messages |
| `time_utils.py` | Add new formatting functions |
| `audit.py` | Add new audit event types |
| `security.py` | Add new permission checks |
| `logging.py` | Modify JSON format |
| `trace.py` | Add trace entry fields |

### 6.2 CAUTION ZONES - Coordinate with Guardian

These modules require architectural review:

| Module | Caution Areas |
|--------|---------------|
| `rotation.py` | Algorithm changes, scoring weights |
| `health.py` | API response parsing, new providers |
| `auth_accounts.py` | New auth formats, provider logic |
| `config.py` | New configuration options |
| `state.py` | State schema changes |

### 6.3 RESTRICTED ZONES - Require Approval

These modules impact system stability:

| Module | Restriction |
|--------|-------------|
| `proxy.py` | Any changes to request flow |
| `cli.py` | New commands, option changes |
| `ui.py` | Breaking changes to output format |

---

## 7. Architecture Decision Records (ADRs)

### ADR-001: Frozen Dataclass for Config

**Status:** Accepted  
**Context:** Configuration must be thread-safe for async proxy operations  
**Decision:** Use `@dataclass(frozen=True)` for Config  
**Consequences:** 
- ✅ Thread-safe by design
- ✅ Immutable prevents accidental mutation
- ❌ Requires full replacement for updates

### ADR-002: File-Based State Storage

**Status:** Accepted  
**Context:** Simple deployment, single-user scenario  
**Decision:** Use JSON file with file locking  
**Consequences:**
- ✅ Simple backup and inspection
- ✅ No external dependencies
- ❌ No horizontal scaling
- ❌ Potential race conditions

### ADR-003: Async Proxy with Sync State Writes

**Status:** Accepted  
**Context:** FastAPI requires async, file I/O is blocking  
**Decision:** Use `asyncio.to_thread()` for state operations  
**Consequences:**
- ✅ Prevents blocking event loop
- ✅ Maintains file consistency
- ⚠️ Slight performance overhead

### ADR-004: Debounced State Persistence

**Status:** Accepted  
**Context:** High-frequency state updates in proxy  
**Decision:** `StateWriter` with 50ms debounce  
**Consequences:**
- ✅ Reduces disk I/O
- ✅ Batches rapid updates
- ⚠️ Potential data loss on crash

### ADR-005: Schema Versioning for State

**Status:** Accepted  
**Context:** State format may evolve  
**Decision:** `schema_version` field with migration  
**Consequences:**
- ✅ Backward compatibility
- ✅ Clear upgrade path
- ⚠️ Migration code accumulates

### ADR-006: Rich Library for CLI Output

**Status:** Accepted  
**Context:** Need attractive, informative dashboards  
**Decision:** Use Rich library for all output  
**Consequences:**
- ✅ Beautiful output
- ✅ Tables, panels, colors
- ❌ Terminal compatibility issues
- ❌ Harder to parse programmatically

### ADR-007: Typer for CLI Framework

**Status:** Accepted  
**Context:** Modern Python CLI requirements  
**Decision:** Use Typer with type hints  
**Consequences:**
- ✅ Automatic help generation
- ✅ Type validation
- ✅ Shell completion
- ❌ Learning curve for contributors

---

## 8. Boundary Protection Recommendations

### 8.1 Immediate Actions (This Sprint)

1. **Split `proxy.py`** into focused modules:
   ```
   proxy/
   ├── __init__.py
   ├── server.py      # FastAPI app creation
   ├── limiter.py     # Rate limiting
   ├── context.py     # ProxyContext
   └── writers.py     # StateWriter, TraceWriter
   ```

2. **Extract CLI commands** from `cli.py`:
   ```
   cli/
   ├── __init__.py
   ├── main.py        # App definition
   ├── proxy_cmds.py  # Proxy commands
   ├── rotate_cmds.py # Rotation commands
   └── status_cmds.py # Status commands
   ```

3. **Add explicit Strategy pattern** for rotation:
   ```python
   class RotationStrategy(ABC):
       @abstractmethod
       def select_key(self, ...) -> Optional[KeyRecord]: ...
   ```

### 8.2 Short-term (Next 2 Sprints)

1. **Repository Pattern** for state access
2. **Configuration validation** with Pydantic
3. **Structured logging** with correlation IDs
4. **Health check endpoint** for proxy

### 8.3 Long-term (Next Quarter)

1. **Plugin architecture** for auth providers
2. **Metrics export** (Prometheus/OpenTelemetry)
3. **State backend** abstraction (Redis, etc.)

---

## 9. Agent Coordination Guidelines

### 9.1 Before Starting Work

1. **Check this document** for module classification
2. **Identify the zone** (Safe/Caution/Restricted)
3. **Run tests** to establish baseline
4. **Communicate intent** in restricted zones

### 9.2 During Development

1. **Maintain SRP** - new functions < 50 lines
2. **Preserve interfaces** - no breaking changes
3. **Add tests** - maintain 95% coverage
4. **Document changes** - update ADRs if needed

### 9.3 Before Submitting

1. **Run full test suite** - `pytest --cov`
2. **Check for cycles** - `pydeps` or similar
3. **Verify imports** - no new cross-layer violations
4. **Update this document** - if architecture changes

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| State corruption | Low | High | Backups, atomic writes |
| Proxy deadlock | Low | High | Timeouts, circuit breakers |
| Rate limit bypass | Low | Medium | Per-key limits, tests |
| Config injection | Low | High | Input validation, allowlist |
| File permission leaks | Medium | Medium | Enforcement, warnings |
| Memory leak in proxy | Medium | Medium | Bounded queues, limits |

---

## 11. Conclusion

The KMI Manager CLI demonstrates **solid architectural foundations** with:
- Clear separation of concerns
- Appropriate use of dataclasses
- Good test coverage
- Thoughtful security considerations

**Required attention:**
- Module size reduction (proxy.py, cli.py)
- Explicit strategy patterns
- Documentation of public APIs

**Architecture Guardian Approval:** ⚠️ **Conditional**

Work may proceed with:
1. No new features in `proxy.py` until refactoring
2. All changes reviewed against this document
3. ADR process for significant architectural decisions

---

*"Architecture is the decisions that you wish you could get right early in a project."* - Martin Fowler

*"The only way to go fast is to go well."* - Robert C. Martin

*"The model is not the diagram; the model is the concepts and the constraints."* - Eric Evans

---

**Document Version:** 1.0  
**Next Review Date:** After major refactoring or v0.2.0 release
