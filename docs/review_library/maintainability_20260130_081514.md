# Maintainability Review - KMI Manager CLI (Python)
Date: 2026-01-30
Scope: `src/`, `tests/`, `docs/` with emphasis on CLI, proxy, state/trace, and UI rendering

## Expert Bio
I have 30 years of experience building and sustaining developer tools, CLI platforms, and long-lived Python services. I have led multi-year refactors, designed operational control planes, and stabilized proxy-style systems that run under continuous change. My focus is reducing entropy through clear module boundaries, safe persistence patterns, and reliable observability. I regularly review CLI and API gateway code where long-term maintainability matters more than novelty.

## Executive Summary
KMI Manager CLI is well structured around its core domains (config, auth/accounts, keys, rotation, health, proxy, trace/UI), and recent improvements like file locking and atomic writes are a strong step forward. The primary maintainability risks now concentrate in concurrent request handling (shared in-memory state + synchronous disk writes), large UI functions that embed business logic, and duplicated parsing paths for auth/config data. Addressing these will improve long-term sustainability and make future policy or provider changes safer and faster.

## Findings (ordered by severity)

### High
1) **Shared mutable state in async request path without in-memory synchronization**
- `src/kmi_manager_cli/proxy.py` mutates `State` from concurrent async handlers (selection, counters, exhaustion) without an `asyncio.Lock` or transactional store.
- Impact: lost updates, inconsistent rotation behavior, and hard-to-reproduce bugs under load.
- Maintainability risk: concurrency bugs are costly to debug and erode trust in rotation/health metrics.

2) **Synchronous file I/O inside the async proxy handler**
- `save_state` and `append_trace` perform disk writes on every request (`proxy.py` -> `state.py`, `trace.py`).
- Impact: event loop blocking, latency spikes, and throughput collapse as load grows.
- Maintainability risk: performance regressions are easy to introduce and hard to diagnose.

### Medium
3) **UI rendering mixes presentation with domain heuristics**
- `src/kmi_manager_cli/ui.py` includes label aliasing, account matching, usage heuristics, and selection logic mixed into rendering code.
- Impact: high cognitive load; small UI changes can break business logic or vice versa.
- Maintainability risk: the UI becomes a second source of truth for domain behavior.

4) **Health parsing and scoring are tightly coupled to provider quirks**
- `src/kmi_manager_cli/health.py` both parses provider payloads and enforces policy thresholds used by `rotation.py`.
- Impact: adding new providers or policy changes requires edits across multiple modules.
- Maintainability risk: policy churn increases code churn and regression risk.

5) **Custom TOML parsing and duplicated auth scanning**
- `auth_accounts.py` implements a minimal TOML parser and scans auths; `keys.py` separately scans env metadata and files.
- Impact: drift between parsers and assumptions about labels/base URLs.
- Maintainability risk: future config changes or edge cases become brittle.

6) **Dual package layout and import path shims**
- `kmi_manager_cli/__init__.py` extends `__path__`, while `sitecustomize.py` injects `src/` into `sys.path`.
- Impact: import resolution is harder to reason about; tooling can behave inconsistently.
- Maintainability risk: onboarding and packaging issues over time.

### Low / Hygiene
7) **CLI interface duplication**
- Both flags and subcommands implement similar behaviors in `cli.py`.
- Impact: higher surface area for drift and inconsistent help output.

8) **State/trace formats lack explicit schema versioning**
- `state.json` and `trace.jsonl` have no version field or migration strategy.
- Impact: future format changes risk silent breakage or data loss.

9) **Minor repo hygiene drift**
- Empty `src/kmi_manager_cli/commands/` directory and parallel `Docs/` vs `docs/` can confuse contributors.

## Structural Strengths
- Clear domain separation with readable dataclasses and explicit config defaults.
- File locking and atomic writes reduce corruption risk for state/trace files.
- Tests cover core logic (rotation, state, health, proxy basics) and include a UI smoke test.
- Proxy includes rate limiting, retry logic, and structured logging which aids operational debugging.

## Entropy Risk Themes
- **Concurrency and persistence**: shared mutable state + synchronous I/O in the async proxy path is the dominant risk.
- **UI complexity**: large rendering functions are an entropy sink without clear boundaries.
- **Boundary clarity**: parsing, policy, and selection logic span multiple modules.

## Recommendations

### Immediate (1-2 days)
- Add an `asyncio.Lock` around in-memory state mutation in the proxy, or introduce a small `StateStore` with atomic update methods.
- Move state/trace writes off the request path (buffer + background writer), or batch writes with a short debounce.
- Add a schema version field to `state.json` and `trace.jsonl` to future-proof format changes.

### Near-term (1-2 weeks)
- Split `render_accounts_health_dashboard` into small helpers (status line, limits, aliasing, action line) and add snapshot tests.
- Extract provider parsing into an adapter layer and keep scoring policy in one place.
- Replace the custom TOML parser with a lightweight TOML library to reduce edge cases.

### Mid-term
- Consolidate the package layout to `src/` only and remove import shims.
- Unify CLI entrypoints to reduce duplicated code paths.

## Testing Gaps
- No concurrency tests for proxy state updates or multi-request correctness.
- No performance tests for async proxy under load (I/O, trace writes, rate limiting).
- Limited UI snapshot coverage for accounts dashboard variants and aliasing logic.

## Suggested Quick Wins
- Add a small in-memory queue for trace events to decouple writes from request latency.
- Document the state/trace schema in `docs/` for future contributors.
- Remove empty directories and normalize docs structure.
