# Rotation Protection Plan (Exhausted / Payment / Rate Limited Keys)

## Findings (critical read)
- Providers recommend exponential backoff on 429 and honoring Retry-After. This implies per-key cooldown logic rather than retrying the same key immediately.
- Payment-required / billing errors should be treated as hard blocks and removed from rotation until manual or periodic recheck.
- /usages is the best health signal but is too slow for the hot path; it should be cached and refreshed in the background.
- A circuit-breaker pattern prevents repeated 5xx loops and avoids cascading failures.

## Goals
- Keep request-path latency flat (no extra network call per request).
- Avoid repeatedly sending traffic to exhausted or unpaid keys.
- Provide explicit operator controls (manual clear/recheck, clear visibility).
- Preserve current auto-rotation behavior unless policy requires stricter selection.

## Non-goals
- No multi-process shared cache or distributed coordination.
- No provider-specific SDK integration beyond HTTP + /usages.

## Proposed design

### 1) Error classification (request path)
- 401: blocked (auth error).
- 402 or payment/billing tokens in error payload: blocked (payment required).
- 403: warn + cooldown (tunable; avoid permanent block unless provider confirms).
- 429: exhausted + cooldown, honor Retry-After.
- 5xx: short cooldown + circuit breaker (avoid hammering).

### 2) State model (state.json)
- blocked_until, blocked_reason (payment/auth).
- exhausted_until (quota/rate).
- Optional: error streak counters + last_error_at for circuit breaker.

### 3) Selection policy
- Skip disabled, blocked, exhausted keys.
- Auto-rotate: prefer healthy keys, fallback to warn.
- Optional strict mode: require cached usage_ok to be true.
- Fail-open on empty cache to avoid 503 at startup (configurable).
- If no eligible keys: return 503 with remediation text.

### 4) Background health refresh
- Periodic refresh of /usages into in-memory cache.
- Cache TTL (e.g., 300s to 900s).
- Recheck a limited number of blocked keys per interval to avoid stampede.

### 5) Circuit breaker
- If error rate or streak crosses threshold, apply cooldown.
- Keep cooldown short for 5xx and use exponential backoff for repeated failures.

### 6) Observability and control
- Trace: include payment_required and cooldown causes.
- Logs: key_blocked, key_exhausted, cooldown applied, recheck cleared.
- CLI: doctor options to recheck and clear blocklist.

## Implementation steps (ordered)
1) Add state fields for blocked/exhausted metadata and (optional) backoff counters.
2) Implement error classification in proxy and mark blocked/exhausted accordingly.
3) Update selection logic to skip blocked/exhausted and honor strict usage_ok mode.
4) Add background health refresh loop (cache-only on hot path).
5) Add background blocklist recheck with rate limits.
6) Extend trace/logging for block/exhaust/recheck events.
7) Add CLI controls for manual clear/recheck.
8) Add config knobs and docs (env example + README).
9) Tests: rotation selection, payment block, retry-after cooldown, blocklist recheck.

## Testing plan
- Unit: select_key_for_request skips blocked/exhausted and honors usage_ok.
- Scenario: 402 + payment token => blocked + removed from rotation.
- Scenario: 429 => exhausted with Retry-After cooldown.
- Scenario: 5xx => short cooldown and re-eligibility after delay.
- Background: health refresh updates cache without blocking request path.
- Doctor: recheck clears blocked keys on successful /usages.

## Risks and mitigations
- Risk: cache empty on startup -> no eligible keys in strict mode.
  - Mitigation: allow fail-open or require a warm-up refresh.
- Risk: background refresh spikes upstream usage.
  - Mitigation: stagger refresh, limit per-interval rechecks.
- Risk: provider-specific error formats.
  - Mitigation: keep token list configurable and add parsing for known fields.
