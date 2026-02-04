# 🧙 UX Seer Review: KMI Manager CLI

**Project:** KMI Manager CLI  
**Target Users:** Developers using the Kimi API  
**Date:** 2026-02-04  
**Overall UX Grade:** B+

---

## Executive Summary

The KMI Manager CLI demonstrates solid UX foundations with rich terminal output, comprehensive error messages, and extensive documentation. However, there are several areas where the user experience could be significantly improved—particularly around configuration discoverability, error actionability, and CLI consistency.

---

## 🔴 Critical UX Blockers

### 1. **Default Dry-Run Mode is Confusing**

**Current Behavior:**
```
MODE: DRY-RUN (upstream requests are simulated).
```

**Problem:** The default dry-run mode (`KMI_DRY_RUN=1`) silently simulates all upstream requests. Users following the quickstart guide will be confused when their configuration changes don't actually apply or when the proxy doesn't actually proxy requests.

**Impact:** 🔴 HIGH - Users may spend significant time debugging why keys aren't rotating or why the proxy isn't working.

**Recommendation:** 
- Add a prominent warning on first run: 
  ```
  ⚠️  WARNING: Running in DRY-RUN mode. Set KMI_DRY_RUN=0 to enable live traffic.
  ```
- Consider an interactive prompt on first run to confirm the mode

---

### 2. **Auto-Rotation Policy is Too Restrictive Without Clear Guidance**

**Current Behavior:**
```python
typer.echo(
    "Auto-rotation is disabled by policy (KMI_AUTO_ROTATE_ALLOWED=false)."
)
```

**Problem:** The error message doesn't explain WHY it's disabled by policy or provide context about compliance requirements.

**Recommendation:**
```python
typer.echo(
    "Auto-rotation is disabled by policy.\n"
    "Reason: Auto-rotation must comply with your provider's Terms of Service.\n"
    "To enable: Set KMI_AUTO_ROTATE_ALLOWED=1 (ensure compliance first)\n"
    "See: https://docs.kimi.com/api/rotation-policy"
)
```

---

### 3. **Config Error Messages Don't Show Valid Options**

**Current Behavior:**
```python
typer.echo(f"Config error: {exc}")
typer.echo("Hint: check .env or KMI_* environment variables.")
```

**Problem:** The error message is too vague. Users don't know which specific variable failed or what valid values look like.

**Example Issue:** When `KMI_PROXY_BASE_PATH` doesn't start with `/`, the error only says "must start with '/'" without showing the invalid value.

**Recommendation:** Include the variable name, invalid value, and expected format in all validation errors.

---

## 🟡 Usability Improvements

### 4. **Inconsistent Command Naming**

**Current Issue:**
- `--auto_rotate` (underscore) vs `--rotate` (no underscore)
- `rotate auto` vs `rotate off` (inconsistent verb form)
- `--health` vs `health` command (duplicated functionality)

**Impact:** Users must remember which commands use underscores and which don't.

**Recommendation:** 
- Standardize on kebab-case: `--auto-rotate`, `--rotate-on-tie`
- Deprecate underscore variants with warnings
- Consider consolidating `--health` flag and `health` command

---

### 5. **Help Text is Information Overload**

**Current APP_HELP:**
```
KMI Manager CLI for rotation, proxy, and tracing.
Version: {__version__}
Config defaults:
  KMI_AUTHS_DIR=_auths
  KMI_PROXY_LISTEN=127.0.0.1:54123
  ... (20+ lines)
```

**Problem:** The default help dumps all configuration defaults, making it hard to find actual usage information.

**Recommendation:** 
- Move defaults to a `kmi config --defaults` command
- Keep main help focused on commands and quick examples
- Add a `kmi examples` command for common workflows

---

### 6. **Missing Progress Indicators for Long Operations**

**Current Issue:** Health checks and E2E tests can take significant time but don't show progress.

**E2E Progress (Good Example):**
```
sent=25/50 trace=12 keys=2/3 confidence=85% errors=0
```

**Health Check (Needs Improvement):**
```python
# Currently no progress indication
health = get_accounts_health(config, accounts, state, force_real=False)
```

**Recommendation:** Add spinners or progress bars for operations that make multiple API calls.

---

### 7. **Trace TUI Lacks Navigation Help**

**Current:**
```python
console.print(f"Tracing {path} (Ctrl+C to exit)")
```

**Problem:** The trace TUI shows live data but doesn't explain what the columns mean or how to interpret confidence scores.

**Recommendation:** Add a help overlay (press `?`) showing:
- Column definitions
- Confidence score interpretation
- Keyboard shortcuts

---

### 8. **Rotation Reason Messages Could Be More User-Friendly**

**Current Examples:**
```python
"Current key ties for best remaining quota (85%). Keeping current over backup-key."
"Current key has higher remaining quota (85%), next best backup-key has 45%."
```

**Better Examples:**
```python
"✓ Keeping 'prod-key-1' (85% quota available) - no better option found"
"✓ Staying on 'prod-key-1' - it has 40% more quota than 'backup-key' (85% vs 45%)"
```

---

## ✨ Enhancement Suggestions

### 9. **Add a `kmi init` Command**

**Gap:** New users must manually create `_auths/` directory and `.env` file.

**Proposed:**
```bash
$ kmi init
? Auth directory (_auths): _auths
? Create sample auth file? (Y/n): Y
? API Key: sk-xxxxxxxx
? Key label: production
✓ Created _auths/production.env
? Enable auto-rotation? (y/N): N
? Dry-run mode? (Y/n): Y
✓ Created .env with sensible defaults
✓ Run 'kmi doctor' to verify setup
```

---

### 10. **Enhance Doctor Output with Next Steps**

**Current:**
```
KMI Doctor
✅ Env file: .env
❌ Auth keys: no keys found in _auths/
    fix: Add auth files in _auths/ or set KMI_AUTHS_DIR.
⚠️ Proxy: not running on 127.0.0.1:54123
    fix: Run: kmi proxy
```

**Enhanced:**
```
KMI Doctor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Env file: .env
❌ Auth keys: no keys found in _auths/
    ├─ Quick fix: kmi init
    ├─ Manual: Create _auths/mykey.env with KMI_API_KEY=sk-...
    └─ Docs: https://github.com/org/repo/blob/main/docs/auths.md

⚠️ Proxy: not running on 127.0.0.1:54123
    ├─ Start: kmi proxy
    ├─ Check logs: kmi proxy-logs
    └─ Troubleshoot: kmi doctor --verbose

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Summary: 1 error, 1 warning, 3 OK
Next step: Add auth keys (see fix above)
```

---

### 11. **Add Key Validation on Load**

**Current:** Invalid keys are only detected when making requests.

**Proposed:**
```bash
$ kmi --all
⚠️  Warning: Key 'prod-1' has invalid format (expected sk-...)
⚠️  Warning: Key 'staging' appears to be a test key
✓ 3 keys loaded (2 valid, 1 test, 0 invalid)
```

---

### 12. **Improve Config Validation Messages**

**Current:**
```python
raise ValueError(f"{name} must use https://")
# Results in: "KMI_UPSTREAM_BASE_URL must use https://"
```

**Enhanced:**
```python
raise ValueError(
    f"{name} must use https://\n"
    f"  Current value: {value}\n"
    f"  Example: https://api.kimi.com/coding/v1\n"
    f"  To override (insecure): set {name}_INSECURE=1"
)
```

---

## Specific Examples: Confusing vs Ideal Messages

### Configuration Errors

| Scenario | Current | Ideal |
|----------|---------|-------|
| Invalid URL scheme | `KMI_UPSTREAM_BASE_URL must use https://` | `KMI_UPSTREAM_BASE_URL must use https:// (got: "http://api.example.com")` |
| Empty auth dir | `No API keys found in _auths/` | `No API keys found in _auths/ (expected: *.env, *.toml, *.json files with KMI_API_KEY)` |
| Blocked key | `Auto-rotation is disabled by policy` | `Auto-rotation disabled. Compliance note: Ensure your provider allows key rotation per Terms of Service before enabling.` |

### Success Messages

| Scenario | Current | Ideal |
|----------|---------|-------|
| Rotation | `Rotation complete` | `✓ Rotated to 'prod-key-2' (90% quota, 0% error rate)` |
| Proxy start | `✅ Proxy started in background` | `✓ Proxy started on http://127.0.0.1:54123 (PID: 12345)\n  Test: curl http://127.0.0.1:54123/kmi-rotor/v1/models` |
| E2E complete | `E2E OK: confidence=98%` | `✓ E2E test passed (98% confidence, 50/50 requests, 3 keys used)` |

### Warning Messages

| Scenario | Current | Ideal |
|----------|---------|-------|
| Dry run mode | `MODE: DRY-RUN` | `⚠️  DRY-RUN MODE: Requests are simulated. Set KMI_DRY_RUN=0 for live traffic.` |
| Low quota | (in health table) | `⚠️  Key 'prod-1' at 95% quota - consider rotation` |
| TLS not terminated | `Note: TLS termination required...` | `⚠️  Remote proxy without TLS. Set KMI_PROXY_TLS_TERMINATED=1 or KMI_PROXY_REQUIRE_TLS=0` |

---

## Documentation Analysis

### README.md Strengths ✅
- Clear quickstart section
- Comprehensive environment variable listing
- Security considerations are prominent
- Notes section is valuable for edge cases

### README.md Weaknesses ⚠️
1. **Too many notes** - The Notes section (lines 37-59) has 20+ bullet points; critical info gets lost
2. **No troubleshooting section** - Common errors aren't addressed
3. **Missing architecture diagram** - AGENTS.md has it, README should too
4. **No screenshot of the UI** - Users don't know what to expect

### AGENTS.md Strengths ✅
- Excellent architecture diagram
- Comprehensive module reference
- Clear patterns and examples
- Good troubleshooting section

### AGENTS.md Weaknesses ⚠️
- Some default values are out of sync with config.py
- Missing section on upgrading between versions

---

## Configuration Experience

### Environment Variables

**Well-designed:**
- Consistent `KMI_` prefix
- Boolean flags accept multiple formats (`1`, `true`, `yes`, `on`)
- Sensible defaults documented

**Could Improve:**
- No validation warnings for unknown variables (typos silently ignored)
- No config file schema validation
- No interactive config wizard

### Suggested Config Improvements

```bash
# Add config validation command
$ kmi config --validate
✓ KMI_AUTHS_DIR: _auths (exists)
✓ KMI_PROXY_LISTEN: 127.0.0.1:54123 (port available)
⚠️ KMI_UPSTREAM_BASE_URL: https://api.kimi.com/coding/v1 (unreachable)
✓ All other settings valid

# Add config explain command
$ kmi config --explain KMI_FAIL_OPEN_ON_EMPTY_CACHE
KMI_FAIL_OPEN_ON_EMPTY_CACHE (default: true)
  When true: Allow proxy requests even when usage cache is empty
  When false: Block requests until usage data is fetched
  Impact: Set to false for strict quota enforcement
```

---

## Observability Analysis

### Logging ✅ Good
- Structured JSON logging
- Separate app and daemon logs
- Timezone-aware timestamps
- Rotation with backups

### Tracing ✅ Good
- Live TUI with highlighting
- Distribution tracking
- Confidence scoring

### Could Improve
1. **No request latency tracking** in trace output
2. **No error aggregation** - Each error is logged individually
3. **No metrics export** - No Prometheus/StatsD integration

---

## Summary & Action Items

### Immediate (P0)
1. **Fix dry-run messaging** - Add prominent warnings
2. **Improve config error messages** - Show invalid values and examples
3. **Add `kmi init` command** - Guide new users through setup

### Short-term (P1)
4. Standardize command naming (kebab-case)
5. Add progress indicators for health checks
6. Enhance `kmi doctor` with contextual next steps

### Long-term (P2)
7. Add interactive config wizard
8. Create comprehensive troubleshooting guide
9. Add request latency tracking to traces

---

## Grading Breakdown

| Category | Grade | Notes |
|----------|-------|-------|
| CLI Structure | B | Good command organization, inconsistent naming |
| Error Messages | B+ | Actionable but could show more context |
| Documentation | A- | Comprehensive but information-dense |
| Configuration | B | Flexible but lacks validation and wizard |
| Observability | A | Excellent logging and tracing |
| Visual Design | A- | Rich output, good use of colors/emoji |
| Onboarding | C | No guided setup, dry-run trap |

**Overall: B+** - Solid foundation with room for polish in onboarding and consistency.
