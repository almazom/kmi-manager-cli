# Maintainability Review — KMI Manager CLI (Python)
Date: 2026-01-29
Scope: `src/`, `tests/`, `docs/` (with emphasis on CLI, proxy, state/trace, and UI)

## Expert Bio
I’ve spent 30 years building and maintaining developer tools, distributed systems, and long-lived Python services. My career has included leading platform teams, refactoring legacy codebases at scale, and designing operational tooling that survives years of production churn. I specialize in reducing entropy through architecture, observability, and pragmatic automation. I’m also a frequent reviewer of CLI and API gateway code where reliability and maintainability matter more than novelty.

## Executive Summary
KMI Manager CLI is generally well-structured with clear domain modules, readable dataclasses, and a consistent use of configuration and state. The biggest maintainability risks are a couple of runtime-breaking bugs, state/trace file concurrency hazards, and growing UI complexity. Addressing a small set of issues (imports, undefined variables, file locking, and I/O patterns) would significantly improve reliability and reduce long-term entropy.

## Findings (ordered by severity)

### High
1) **Runtime NameError: `Account` used without import**
- `src/kmi_manager_cli/cli.py:100` uses `Account(...)` without importing it.
- Impact: calling `kmi --health` or `kmi health` can crash when current account maps to auths.

2) **Runtime error in UI: undefined `reset_line` and optional `last_used_line`**
- `src/kmi_manager_cli/ui.py:224-251` references `reset_line` (undefined) and passes `last_used_line` which can be `None` into `Text.assemble`.
- Impact: `render_health_dashboard` can crash even on normal data, making the dashboard brittle.

3) **No file locking or atomic writes for state/trace in a concurrent server**
- `src/kmi_manager_cli/state.py:51-83` writes state via `write_text()` with no lock or atomic rename.
- `src/kmi_manager_cli/trace.py:20-34` appends JSONL without locking.
- `src/kmi_manager_cli/proxy.py:49-140` mutates shared `State` and writes to disk per request.
- Impact: concurrent requests (or multiple processes) can corrupt `~/.kmi/state.json` / `trace.jsonl` or lose updates.

### Medium
4) **`load_state` writes on every read**
- `src/kmi_manager_cli/state.py:59-83` always calls `save_state()` after reading.
- Impact: needless disk churn; worse, can overwrite newer state in multi-process scenarios.

5) **Trace UI and loader reread entire file repeatedly**
- `src/kmi_manager_cli/trace.py:36-49` loads full file into memory to read last N lines.
- `src/kmi_manager_cli/trace_tui.py:28-43` does this every refresh (default 1s).
- Impact: performance degrades as trace grows, and the UI cost scales with file size.

6) **State shared across async requests without synchronization**
- `src/kmi_manager_cli/proxy.py:49-140` mutates `State` in async handlers.
- Impact: interleaved updates can lead to miscounted request stats and incorrect rotation decisions.

7) **Package layout duplication can confuse imports**
- `kmi_manager_cli/__init__.py` extends `__path__` into `src/kmi_manager_cli` while also being a top-level package.
- Impact: subtle import ambiguities, harder packaging/debugging, increased entropy.

### Low / Readability
8) **UI function complexity and mixed styles**
- `render_accounts_health_dashboard` is very large (multi-branch logic, nested heuristics), while `render_health_dashboard` builds `Text` differently.
- Impact: hard to test, harder to change without regressions.

9) **Typo + inconsistent labels**
- `_status_meta` and display paths use `EXCAUSTED` (misspelled) in `src/kmi_manager_cli/ui.py`.
- Impact: minor but creates confusing UI terminology.

10) **Missing `.gitignore`; cache artifacts in repo**
- `tests/__pycache__` and `.pytest_cache` exist; there is no `.gitignore` at repo root.
- Impact: noise in diffs, risk of accidental commits of transient files.

11) **CLI UX duplication**
- There are both flags and commands for `rotate`, `trace`, and `health` in `src/kmi_manager_cli/cli.py`.
- Impact: two code paths to keep in sync; help output may confuse users.

## Structural Strengths
- Clear separation of concerns (config, auth/accounts, keys, rotation, health, proxy, trace/UI).
- Good use of dataclasses for state and health modeling.
- Tests exist for core logic (rotation, state, proxy, health) which is a solid baseline.
- Defaults are centralized in `config.py`, avoiding magic values spread across the codebase.

## Entropy Risk Themes
- **Concurrency & persistence:** state/trace/log I/O is not concurrency-safe; this is the highest long-term risk.
- **UI complexity:** large, intertwined UI logic will become fragile without modularization.
- **Repo hygiene:** duplicate package layout and missing ignore rules will accumulate friction over time.

## Recommendations

### Immediate (1–2 days)
- Import `Account` in `cli.py` and fix `render_health_dashboard` to build lines defensively (skip `None`) and define/rename `reset_line`.
- Add file locks + atomic writes for `state.json` and `trace.jsonl` (e.g., `portalocker` or `fcntl` with temp file + rename).
- Add a size guard / rolling policy for trace and log files.

### Near-term (1–2 weeks)
- Introduce a small persistence layer (`StateStore`, `TraceStore`) to centralize I/O, locking, and schema migration.
- Replace `trace_tui` full-file reads with a tailing approach or incremental file pointer.
- Consolidate CLI entrypoints: choose either commands or flags as the primary interface, reduce duplication.

### Mid-term
- Simplify UI rendering by splitting `render_accounts_health_dashboard` into smaller composable helpers (e.g., `build_status_line`, `build_limits_lines`, `build_account_header`).
- Unify package layout to pure `src/` (remove top-level `kmi_manager_cli/` shim or make it a proper namespace package).

## Testing Gaps
- No tests cover `render_health_dashboard` / UI output; add snapshot tests with `Console(record=True)`.
- No tests for state/trace concurrency or file corruption scenarios.
- Health fetch tests don’t cover API error paths or malformed payloads.

## Suggested Quick Wins
- Add `.gitignore` for `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, and `*.pyc`.
- Add a lightweight logging line when `fetch_usage` fails to aid diagnostics.
- Normalize status labels (“EXHAUSTED”) for UI clarity.

---
If you want, I can propose a concrete patch set for the top 3 issues (import fix, UI crash fix, atomic file writes + locking) and add a minimal test to prevent regression.
