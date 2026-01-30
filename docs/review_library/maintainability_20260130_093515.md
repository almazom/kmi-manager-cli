# Maintainability Review
Suggested filename: docs/review_library/maintainability_20260130_093515.md

I have spent roughly 30 years building and maintaining developer tools, API gateways, and CLI ecosystems across teams of all sizes. Over that time, the systems that lasted longest were the ones that kept state transitions explicit, configuration parsing centralized, and concurrency paths testable. I have guided multiple Python services through long-lived refactors, so I focus on the quiet sources of entropy: duplicated parsing logic, hidden coupling, and async side effects. I will keep this review focused on the maintainability levers that most reduce complexity and risk over the next few years.

## Strengths
- Clear separation of concerns (config, auth parsing, rotation, state, proxy, trace) keeps modules cohesive and easy to reason about. See `src/kmi_manager_cli/config.py`, `src/kmi_manager_cli/rotation.py`, `src/kmi_manager_cli/state.py`.
- Defensive IO patterns (file locks + atomic writes) reduce state corruption risk and make later migrations safer. See `src/kmi_manager_cli/locking.py`, `src/kmi_manager_cli/state.py`.
- Solid test surface for core behavior (CLI, rotation, proxy, health) gives a good baseline for future refactors. See `tests/test_cli_rotate.py`, `tests/test_proxy.py`, `tests/test_health.py`.
- Safety guardrails are explicit and discoverable (dry-run, allowlist, TLS requirements). See `src/kmi_manager_cli/config.py`, `src/kmi_manager_cli/proxy.py`.

## Maintainability Risks / Entropy Hotspots
- Global rate limiting looks incomplete and confusing: `RateLimiter.allow()` returns for the "no limits" case but never enforces limits, while `KeyedRateLimiter.allow()` contains unreachable duplicated logic after a return. This is a correctness risk and a maintenance trap. `src/kmi_manager_cli/proxy.py:114`, `src/kmi_manager_cli/proxy.py:154`.
- Auth file discovery and parsing are duplicated in two places, increasing drift risk (directory traversal and supported extensions are re-implemented). `src/kmi_manager_cli/keys.py:33`, `src/kmi_manager_cli/auth_accounts.py:170`.
- State schema versioning exists but lacks explicit migrations, so future schema changes may silently reset or partially load state. `src/kmi_manager_cli/state.py:14`, `src/kmi_manager_cli/state.py:45`.
- CLI mode handling relies on mutually exclusive flags, which gets harder to extend without accidental conflicts; the logic is already branching-heavy. `src/kmi_manager_cli/cli.py:58`, `src/kmi_manager_cli/cli.py:112`.
- Configuration parsing repeats bool/int parsing in multiple modules and has limited validation for bad values, which makes correctness harder to enforce as the surface grows. `src/kmi_manager_cli/config.py:30`, `src/kmi_manager_cli/keys.py:13`.
- Dual `docs/` and `Docs/` directories can drift or break on case-insensitive filesystems. `docs`, `Docs`.

## Recommendations (Low-Effort to High-Leverage)
- Fix and test global rate limiting: implement `RateLimiter.allow()` fully, delete unreachable code in `KeyedRateLimiter`, and add tests for overall RPS/RPM limits. `src/kmi_manager_cli/proxy.py:114`, `tests/test_proxy.py`.
- Consolidate auth file discovery and metadata parsing into one helper (e.g., single "auth index" module) to remove duplication and enforce consistent extension handling. `src/kmi_manager_cli/keys.py:33`, `src/kmi_manager_cli/auth_accounts.py:170`.
- Add explicit state migrations and migration tests keyed off `schema_version`; start with a tiny migration framework to keep future changes safe. `src/kmi_manager_cli/state.py:14`.
- Centralize config validation (single bool/int parsing helpers + bounds checks) and consider a lightweight typed validator to catch invalid env input earlier. `src/kmi_manager_cli/config.py:30`.
- Consider shifting CLI to more subcommand-driven flows (fewer mutually exclusive flags) to reduce combinatorial complexity as features grow. `src/kmi_manager_cli/cli.py:112`.
- Standardize on a single docs directory (likely `docs/`) and retire or archive `Docs/` to prevent drift. `docs`, `Docs`.
