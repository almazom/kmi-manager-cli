# Architecture Guardian Report
Suggested filename: docs/review_library/architecture_2026-01-30.md

I bring 30 years of software architecture experience across mission-critical systems, financial platforms, and developer tools, with a focus on resilient boundaries and long-term maintainability. Over three decades, I have led designs that balance delivery speed with correctness, applying Fowler/Clean Architecture patterns to keep teams moving safely. I have seen where "small" changes become architectural debt, and I am here to help us avoid that while keeping momentum high. I will aim for crisp guardrails, clear contracts, and verification paths so implementation stays fast and safe.

## Scope Framing (Trunk-Branch-Leaf)
- Trunk (immutable core): key management logic, rotation policy engine, state persistence format, proxy request/response schema.
- Branches (bounded modules): CLI commands (Typer), API proxy (FastAPI), storage adapters (state.json/trace.jsonl/logs), health/tracing subsystems.
- Leaves (safe to change): CLI UX output, logging verbosity/format, test utilities, small helper utilities.

## PEGASUS-5 Gates
- WHAT: Python >= 3.9 CLI + FastAPI proxy for Kimi API key rotation, health, and tracing; single-user local-first; stores `state.json`, `trace.jsonl`, logs.
- SUCCESS: rotation works for manual/auto; proxy correctly forwards and rotates on failure; health endpoints reliable; trace persisted; tests pass.
- CONSTRAINTS: local filesystem state; no multi-user; minimal latency; avoid breaking JSON formats; keep CLI backwards compatible.
- TESTS: unit tests for rotation policy + storage; integration tests for proxy and key failover; contract tests for JSON schemas.

## Layered Architecture Spec
- Presentation: Typer CLI commands + FastAPI endpoints.
- Business: key rotation service, health service, trace service, policy rules.
- Data: repositories for state, trace, log files.
- Infrastructure: HTTP client to upstream Kimi API; config loading; logging adapters.

## Contract and Interface Definitions (recommended)
- `KeyStore` interface: `load()`, `save(state)`, `lock()` optional.
- `RotationPolicy`: `select_key(state, request_ctx) -> key`, `on_failure(key, err)`.
- `TraceSink`: `append(trace_event)`; versioned schema for `trace.jsonl`.
- `ProxyClient`: `send(request, key) -> response`.
- JSON contracts: version fields in `state.json` and `trace.jsonl` records.

## Implementation Guidelines (patterns)
- Repository pattern for file IO; keep file formats isolated from business logic.
- Service layer for rotation and health; no IO in services.
- Controller layer thin: CLI/API should only parse/validate and delegate.
- Avoid cross-module imports: CLI -> services -> repositories -> infra only.

## Verification Framework
- Unit: rotation policy decisions; state transitions; trace event serialization.
- Integration: proxy request flow with simulated upstream errors.
- Contract: JSON schema validation for `state.json` and `trace.jsonl`.
- Regression: ensure CLI commands preserve existing output/flags.

## Protection Mechanisms
- Guardrail paths: `/src/core/**`, `/domain/**`, `/schemas/**` require review.
- Branch boundaries: `/src/services/**`, `/src/repositories/**` only accessed via interfaces.
- Leaf freedom: `/src/cli/**`, `/src/features/**`, `/src/components/**`.

## Complexity Assessment
- Current change request: architectural report only (1-3 points).
- Any change to rotation policy or state schema: 8-13 points, requires review.

## Requirements Traceability Matrix
- Rotation reliability -> RotationPolicy + KeyStore + tests.
- Proxy correctness -> ProxyClient + FastAPI endpoint + integration tests.
- Health and tracing -> HealthService + TraceSink + schema validation.
- Local-first persistence -> repositories for `state.json` / `trace.jsonl`.

## Agent Coordination and Constraints
- Architecture Guardian: define/approve contracts and schema changes.
- Implementation Agent: operates within interfaces; no schema edits without review.
- Review Agent: verifies boundary compliance + tests pass.
- Specialist (optional): security review for key handling and log redaction.

If you want, I can scan the repo and map current files to these boundaries, or draft the initial ADRs and interface stubs.
