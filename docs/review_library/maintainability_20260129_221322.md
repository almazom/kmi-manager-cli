# Maintainability Review — KMI Manager CLI (Python)
Date: 2026-01-29
Scope: `src/`, `tests/`, `docs/` with emphasis on CLI, proxy, state/trace, and UI rendering

## Expert Bio
I have 30 years of experience building and sustaining developer tools, CLI platforms, and long-running backend services in Python and adjacent ecosystems. I have led multi-year refactors, decomposed monoliths into stable modules, and designed operational tooling that remains maintainable under continuous change. My focus is reducing entropy with clear boundaries, safe persistence patterns, and testable seams. I regularly review CLI and proxy-style systems where reliability and operational clarity are more important than novelty.

## Executive Summary
KMI Manager CLI is readable and well organized around its core domains (config, auth/accounts, keys, rotation, health, proxy, trace/UI). The biggest long-term risks are concurrency and persistence safety (state/trace/log I/O in a concurrent proxy), plus UI complexity that is accumulating without clear boundaries. Addressing a small number of correctness and hygiene gaps will materially improve maintainability and reduce future regression risk.

## Findings (ordered by severity)

### High
1) **State and trace I/O in a concurrent server can corrupt or lose data**
- `src/kmi_manager_cli/proxy.py` mutates shared in-memory `State` and writes to disk in async handlers.
- `src/kmi_manager_cli/state.py` and `src/kmi_manager_cli/trace.py` do not centralize concurrency-safe persistence.
- Impact: interleaved requests can clobber state, lose counters, or create partially written files.
- Maintainability risk: hard-to-reproduce bugs and data drift in production.

2) **UI surface is brittle due to large, intertwined rendering functions**
- `src/kmi_manager_cli/ui.py` contains multi-branch logic, heuristics, and formatting in single functions.
- Impact: small feature tweaks are likely to break rendering or produce inconsistent output.
- Maintainability risk: high cognitive load, hard-to-test UI changes.

### Medium
3) **Config and key loading logic is scattered across modules**
- `_auths` scanning, current account loading, and label normalization live across `auth_accounts.py` and `keys.py`.
- Impact: duplicated logic and implicit invariants (labels, base URL selection) are easy to break.
- Maintainability risk: high coupling between parsing and domain logic.

4) **Health and rotation logic intermixes policy with data shaping**
- `health.py` parses provider payloads and applies policy rules; `rotation.py` applies selection logic tightly coupled to health fields.
- Impact: policy changes (e.g., different thresholds) require edits across multiple modules.
- Maintainability risk: difficult to extend to new providers or new scoring policies.

5) **Project layout has two packages with the same name**
- `kmi_manager_cli/` at repo root extends path into `src/kmi_manager_cli`.
- Impact: import resolution can be surprising and increases packaging ambiguity.
- Maintainability risk: confusing for contributors and tooling.

### Low / Hygiene
6) **CLI has two entry styles (flags and subcommands) with overlapping behavior**
- `src/kmi_manager_cli/cli.py` supports both; risk of future drift.
- Impact: duplication increases changeset surface area.

7) **Trace UI and loader do repeated file scans**
- `src/kmi_manager_cli/trace.py` tailing method reads full file content repeatedly and `trace_tui.py` refreshes every second.
- Impact: performance and operational costs grow with file size.

8) **Limited test coverage around rendering and persistence concurrency**
- Tests exist for core logic, but there are no concurrency or snapshot UI tests.
- Impact: regressions in UI and persistence are likely to slip through.

## Structural Strengths
- Domain separation is mostly clean: config, auth, keys, rotation, health, proxy, trace, UI.
- Dataclasses provide strong, readable data modeling.
- Tests exist for rotation, proxy, state basics, and CLI behavior, which is a solid base.
- Defaults are centralized in `config.py`, reducing magic values in code paths.

## Entropy Risk Themes
- **Concurrency and persistence**: shared state writes in a concurrent server are the top risk area.
- **UI complexity**: large rendering functions are a slow drift toward fragility.
- **Boundary clarity**: parsing, policy, and selection logic cross-cut multiple modules.

## Recommendations

### Immediate (1-2 days)
- Introduce a tiny persistence layer (`StateStore`, `TraceStore`) to centralize locking, atomic writes, and schema validation.
- Add a basic concurrency test that runs multiple proxy requests and asserts state consistency.
- Add a trace/log file size policy (rotation or truncation) to prevent unbounded growth.

### Near-term (1-2 weeks)
- Split `render_accounts_health_dashboard` into smaller composable helpers (status line, limits, action line, header) and add snapshot tests using `Console(record=True)`.
- Extract provider parsing from `health.py` into a separate adapter module; keep scoring policy in one place.
- Consolidate CLI interface (either flags or subcommands) to reduce duplicate paths.

### Mid-term
- Standardize package layout to a single `src/` package to eliminate import ambiguity.
- Add a policy configuration object (thresholds, status mapping) that can be unit-tested in isolation.

## Testing Gaps
- No tests for persistence under concurrency or multi-process reads/writes.
- No snapshot tests for UI dashboards.
- Health parsing lacks tests for malformed or partial payloads.

## Suggested Quick Wins
- Add `.gitignore` to exclude `__pycache__/`, `.pytest_cache/`, and `*.pyc` artifacts.
- Add logging on health fetch failures to ease field debugging.
- Create a small, documented data contract for `trace.jsonl` entries to avoid schema drift.
