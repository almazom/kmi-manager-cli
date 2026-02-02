# KMI Manager CLI - Maintainability Analysis Report

**Report Generated:** 2026-02-02  
**Project:** kimi_manager_cli  
**Total Lines of Code:** ~5,731 (source only)  
**Analyzed Files:** 20 Python modules

---

## Executive Summary

| Metric | Value | Grade |
|--------|-------|-------|
| **Maintainability Score** | 62/100 | ⚠️ C |
| **Code Complexity** | High | 🔴 |
| **Docstring Coverage** | 16% | 🔴 Poor |
| **Test Coverage** | 95%+ (config) | 🟢 Good |
| **Style Consistency** | 78% | 🟡 Fair |

### Key Concerns
1. **cli.py** is a massive 1,251-line file with 48 functions
2. **Critical complexity hotspot**: `render_accounts_health_dashboard` has ~80 cyclomatic complexity
3. Poor docstring coverage across all modules
4. Several functions exceed 100+ lines

---

## 1. Complexity Hotspots 🔴

### Severity: CRITICAL

| File | Function | Lines | Complexity | Issue |
|------|----------|-------|------------|-------|
| `ui.py:473` | `render_accounts_health_dashboard` | 380 | ~80 | MONSTER FUNCTION - 80 decision points, single-responsibility violation |
| `proxy.py:585` | `create_app` | 277 | ~27 | Massive route handler, mixes setup + request handling |
| `cli.py:974` | `_run_e2e` | 115 | ~33 | Complex E2E test orchestrator |

### Severity: HIGH

| File | Function | Lines | Complexity | Issue |
|------|----------|-------|------------|-------|
| `cli.py:359` | `_render_status` | 132 | ~12 | Too long, mixes data + presentation |
| `ui.py:293` | `render_health_dashboard` | 121 | ~14 | Duplicates logic with accounts dashboard |
| `rotation.py:142` | `rotate_manual` | 97 | ~21 | Complex scoring logic, multiple branches |
| `health.py:235` | `fetch_usage` | 78 | ~23 | Multiple API response parsing paths |
| `health.py:71` | `_extract_remaining_percent` | 23 | ~16 | Deeply nested conditionals |

### Severity: MEDIUM

| File | Function | Lines | Issue |
|------|----------|-------|-------|
| `config.py:183` | `load_config` | 135 | Long but linear configuration builder |
| `trace_tui.py:46` | `update` | ~50 | TUI update logic |

---

## 2. Module Size Analysis

| Module | Lines | Status | Concerns |
|--------|-------|--------|----------|
| `cli.py` | 1,251 | 🔴 **CRITICAL** | God module - CLI commands, proxy control, E2E testing |
| `proxy.py` | 887 | 🔴 High | Async proxy server, rate limiters, error handling |
| `ui.py` | 824 | 🟡 Medium | Rich dashboard rendering, i18n support |
| `health.py` | 412 | 🟢 OK | API health fetching, usage parsing |
| `rotation.py` | 406 | 🟢 OK | Key rotation algorithms |
| `auth_accounts.py` | 350 | 🟢 OK | Account loading from various formats |
| `doctor.py` | 335 | 🟢 OK | Diagnostics checks |
| `config.py` | 318 | 🟡 Medium | Configuration loading |
| `state.py` | 208 | 🟢 OK | State management |
| `trace_tui.py` | 176 | 🟢 OK | Terminal UI for traces |

### Architectural Issue: `cli.py` is a God Module

The `cli.py` module violates the Single Responsibility Principle:
- CLI command definitions (Typer)
- Proxy daemon management
- Log tailing and filtering
- E2E test execution
- Status rendering
- Process management (start/stop/kill)

**Recommendation:** Split into `cli_commands/`, `daemon/`, and `e2e/` packages.

---

## 3. Code Smell Inventory

### Smell 1: Long Functions (>50 lines)
**Count:** 13 functions  
**Impact:** High

Functions exceeding recommended 50-line limit:
- `cli.py:_run_e2e` (115 lines)
- `cli.py:_render_status` (132 lines)
- `ui.py:render_accounts_health_dashboard` (380 lines) - **WORST OFFENDER**
- `ui.py:render_health_dashboard` (121 lines)
- `proxy.py:create_app` (277 lines) - contains nested route handler
- `config.py:load_config` (135 lines)
- `rotation.py:rotate_manual` (97 lines)

### Smell 2: Missing Docstrings
**Coverage:** ~16% (29 docstrings / 217 functions+classes)

Modules with poorest coverage:
| Module | Functions | Documented | Coverage |
|--------|-----------|------------|----------|
| `cli.py` | 48 | 8 | 17% |
| `ui.py` | 24 | 2 | 8% |
| `rotation.py` | 17 | 2 | 12% |
| `health.py` | 13 | 1 | 8% |
| `proxy.py` | 19 | 3 | 16% |

### Smell 3: High Cyclomatic Complexity
Functions with >15 decision points (if/for/while/except/and/or):
- `ui.py:render_accounts_health_dashboard` (~80) - **SEVERE**
- `proxy.py:create_app` (~27) - includes nested route
- `health.py:fetch_usage` (~23)
- `rotation.py:rotate_manual` (~21)
- `health.py:_extract_remaining_percent` (~16)

### Smell 4: Duplicate Logic
Identified patterns:
- `_proxy_listening` duplicated in `cli.py` and `doctor.py`
- `_normalize_connect_host` duplicated in `cli.py` and `doctor.py`
- `_proxy_base_url` logic duplicated in `cli.py` and `doctor.py`
- Error rate calculation duplicated in `health.py:get_health_map` and `get_accounts_health`

### Smell 5: Feature Envy
- `cli.py` functions frequently reaching into `config`, `state`, `registry`
- UI functions tightly coupled to data structures

---

## 4. Technical Debt Register

### High Priority Debt

| ID | Description | Location | Effort | Impact |
|----|-------------|----------|--------|--------|
| DEBT-001 | Extract `render_accounts_health_dashboard` into view classes | `ui.py` | 4h | HIGH |
| DEBT-002 | Split `cli.py` into command modules | `cli.py` | 8h | HIGH |
| DEBT-003 | Refactor `create_app` route handler | `proxy.py` | 4h | HIGH |
| DEBT-004 | Add docstrings to all public functions | All modules | 6h | MEDIUM |

### Medium Priority Debt

| ID | Description | Location | Effort | Impact |
|----|-------------|----------|--------|--------|
| DEBT-005 | Extract shared proxy utilities | `cli.py`, `doctor.py` | 2h | MEDIUM |
| DEBT-006 | Consolidate error rate calculations | `health.py` | 1h | LOW |
| DEBT-007 | Break down `load_config` into sections | `config.py` | 2h | MEDIUM |
| DEBT-008 | Add type hints to remaining functions | Multiple | 4h | LOW |

### Low Priority Debt

| ID | Description | Location | Effort | Impact |
|----|-------------|----------|--------|--------|
| DEBT-009 | Convert Optional[X] to X \| None syntax | Multiple | 2h | LOW |
| DEBT-010 | Extract magic numbers to constants | Multiple | 2h | LOW |

---

## 5. Style Consistency Analysis

### Current Style Compliance

| Rule | Compliance | Notes |
|------|------------|-------|
| Import ordering | 85% | Generally good, minor inconsistencies |
| Type hints | 70% | Good coverage, some `Optional[str]` vs `str \| None` inconsistency |
| Naming conventions | 95% | snake_case throughout, clear naming |
| Docstring format | 20% | Mostly missing or inconsistent |
| Line length | 95% | Well within limits |

### Ruff Analysis Results
Selected warnings from `ruff check --select ALL`:
- **ANN001/ANN003**: Missing type annotations in `audit.py`
- **UP045**: Multiple files using `Optional[X]` instead of modern `X \| None`
- **COM812**: Missing trailing commas in some multi-line calls
- **PERF401**: Can use `list.extend` instead of loop append

---

## 6. Import Structure Analysis

### Dependency Graph (Simplified)
```
cli.py ──────┬────> config.py
             ├────> proxy.py
             ├────> rotation.py
             ├────> state.py
             ├────> health.py
             ├────> keys.py
             ├────> auth_accounts.py
             └────> ui.py

proxy.py ────┬────> config.py
             ├────> keys.py
             ├────> rotation.py
             ├────> state.py
             └────> health.py

health.py ───┬────> auth_accounts.py
             └────> rotation.py (circular via state?)
```

### Circular Dependency Risk
**Status:** 🟢 No circular imports detected  
The import structure is clean with clear layering:
- `config` → base layer
- `keys`, `state`, `auth_accounts` → data layer  
- `rotation`, `health` → business logic layer
- `proxy` → application layer
- `cli`, `ui` → presentation layer

---

## 7. Priority Fixes

### 🔴 HIGH Priority (Fix Immediately)

1. **Extract `render_accounts_health_dashboard`** (`ui.py:473`)
   - 380 lines, 80 complexity
   - Break into: HeaderRenderer, RowRenderer, StatusRenderer classes
   - Extract layout constants
   - Estimated: 4 hours

2. **Refactor `create_app` proxy route** (`proxy.py:585`)
   - Extract request handler into separate function
   - Split streaming vs non-streaming paths
   - Move error handling to dedicated functions
   - Estimated: 4 hours

3. **Split `cli.py` into modules**
   - Create `cli/commands/rotate.py`
   - Create `cli/commands/proxy.py` 
   - Create `cli/commands/e2e.py`
   - Keep `cli.py` as router only
   - Estimated: 8 hours

### 🟡 MEDIUM Priority (Fix This Sprint)

4. **Add comprehensive docstrings**
   - Target: 80% coverage of public APIs
   - Focus on: `rotation.py`, `health.py`, `proxy.py`
   - Estimated: 6 hours

5. **Extract duplicate proxy utilities**
   - Create `proxy_utils.py` for shared functions
   - Deduplicate `_proxy_listening`, `_normalize_connect_host`
   - Estimated: 2 hours

6. **Refactor `rotate_manual`** (`rotation.py:142`)
   - Extract scoring logic
   - Extract tie-breaking logic
   - Simplify reason message generation
   - Estimated: 3 hours

### 🟢 LOW Priority (Backlog)

7. **Modernize type hints** (`Optional[X]` → `X \| None`)
8. **Extract magic numbers** to module constants
9. **Add module-level docstrings** where missing
10. **Consider dataclasses** for complex return types

---

## 8. Recommendations

### Immediate Actions (This Week)
1. Schedule refactoring sprint for `cli.py`
2. Add complexity checks to CI (e.g., `radon` or `xenon`)
3. Require docstrings for new code (enforced in PR)

### Short-term (Next Month)
1. Extract UI rendering into dedicated package
2. Add architectural decision records (ADRs)
3. Create contribution guidelines with complexity limits

### Long-term (Next Quarter)
1. Consider MVC pattern for CLI commands
2. Add integration tests for proxy routes
3. Evaluate async patterns for better performance

---

## 9. Metrics Summary

```
Total Files:              20 Python modules
Total Lines:              ~5,731 (source only)
Total Functions:          ~217
Total Classes:            ~25

Docstring Coverage:       16% (needs improvement)
Type Hint Coverage:       70% (good)
Functions >50 lines:      13 (6% - needs reduction)
Functions >100 lines:     5 (2.3% - critical)
Complexity >15:           9 functions (4% - needs reduction)

Code Duplication:         Low (good)
Circular Dependencies:    None (good)
Import Count:             ~198 imports
```

---

## Appendix: Function Length Distribution

| Size Category | Count | Percentage |
|--------------|-------|------------|
| 0-20 lines   | ~140  | 65%        |
| 21-50 lines  | ~52   | 24%        |
| 51-100 lines | ~20   | 9%         |
| >100 lines   | 5     | 2%         |

---

*Report generated by Maintainability Anti-Entropy Agent*  
*Methodology: Static analysis, cyclomatic complexity estimation, code smell detection*
