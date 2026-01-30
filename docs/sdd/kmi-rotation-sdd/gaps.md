# KMI Manager CLI - Open Gaps & Questions

> Status: ALL FILLED (ALL GAPS FILLED) | Last updated: 2026-01-29 11:14:26 MSK

## Summary

Total gaps: 6
Filled: 6
Remaining: 0

## Interview Results

### GAP-001: Key file format in `_auths/`

**Question:** What exact format should each key file use?

**Decision:** Per-key `.env` files with `KMI_API_KEY`, `KMI_KEY_LABEL`, optional `KMI_KEY_PRIORITY`, `KMI_KEY_DISABLED`.

**Source:** up2u all

**Confidence:** 95%

**Short Reason:** Matches existing practice of `_auths/` folder and keeps secrets out of code.

**AI Recommendations:**
- Kimi: "Per-key env files are simplest and align with .env workflow." (95%)
- Claude: "Per-file key + metadata keeps rotation simple." (94%)

**User Approval:** Yes (2026-01-29 11:14:26 MSK)

**Implementation Notes:** Loader reads all `*.env` in `_auths/`.

---

### GAP-002: Unique proxy base path/port

**Question:** What unique proxy API base should we use?

**Decision:** `http://127.0.0.1:54123/kmi-rotor/v1` (configurable via `.env`).

**Source:** up2u all

**Confidence:** 95%

**Short Reason:** Unique, non-default path; local-only by default.

**AI Recommendations:**
- Kimi: "Custom base path + port to avoid conflicts." (95%)
- Claude: "Unique prefix prevents banal defaults." (93%)

**User Approval:** Yes (2026-01-29 11:14:26 MSK)

**Implementation Notes:** Proxy strips prefix and forwards to upstream base_url.

---

### GAP-003: Trace window UI

**Question:** TUI or web for trace visualization?

**Decision:** TUI with optional JSONL export (default on).

**Source:** up2u all

**Confidence:** 96%

**Short Reason:** CLI-first workflow, fast to implement, no browser dependency.

**AI Recommendations:**
- Kimi: "TUI fits CLI operators." (96%)
- Claude: "TUI + JSONL is sufficient for audits." (95%)

**User Approval:** Yes (2026-01-29 11:14:26 MSK)

**Implementation Notes:** Use rich for table + live updates.

---

### GAP-004: Confidence metric definition

**Question:** How to compute 95% confidence for round-robin?

**Decision:** Rolling window (N=200). Confidence = 100% - max deviation % from uniform distribution.

**Source:** up2u all

**Confidence:** 95%

**Short Reason:** Simple and explainable; aligns with 95% threshold.

**AI Recommendations:**
- Kimi: "Deviation from uniform is easy to explain to operators." (95%)
- Claude: "Simple deviation metric avoids statistical complexity." (94%)

**User Approval:** Yes (2026-01-29 11:14:26 MSK)

**Implementation Notes:** Display per-key counts + deviation.

---

### GAP-005: Health scoring thresholds

**Question:** What defines healthy/warn/blocked?

**Decision:**
- healthy: remaining >= 20% and error rate < 5%
- warn: remaining < 20% or 429/5xx spikes
- blocked: 401/403 or remaining <= 0

**Source:** up2u all

**Confidence:** 95%

**Short Reason:** Conservative thresholds prevent outages.

**AI Recommendations:**
- Kimi: "Block on auth errors; warn on rate limits." (95%)
- Claude: "Remaining quota threshold is practical." (94%)

**User Approval:** Yes (2026-01-29 11:14:26 MSK)

**Implementation Notes:** Health updated after each request + periodic usage refresh.

---

### GAP-006: Trace log location

**Question:** Where to store trace logs?

**Decision:** `${KMI_STATE_DIR}/trace/trace.jsonl`.

**Source:** up2u all

**Confidence:** 96%

**Short Reason:** Keeps logs localized and predictable.

**AI Recommendations:**
- Kimi: "Separate trace log file for audits." (96%)
- Claude: "Structured JSONL is standard." (95%)

**User Approval:** Yes (2026-01-29 11:14:26 MSK)

**Implementation Notes:** JSONL per request with MSK timestamp.

---

## Decisions Based on Project Analysis

Analyzed existing patterns from:
- `/tmp/tmp.aZ2UpCbylC/kimi-cli/src/kimi_cli/config.py`
- `/tmp/tmp.aZ2UpCbylC/kimi-cli/src/kimi_cli/llm.py`
- `/tmp/tmp.aZ2UpCbylC/kimi-cli/src/kimi_cli/auth/oauth.py`
- `/tmp/tmp.aZ2UpCbylC/kimi-cli/src/kimi_cli/ui/shell/usage.py`
- `/tmp/tmp.aZ2UpCbylC/kimi-cli/packages/kosong/src/kosong/chat_provider/kimi.py`

Key pattern alignments:
1. **Env overrides:** Use `KIMI_API_KEY` and `KIMI_BASE_URL` for dynamic routing.
2. **Usage endpoint:** `/usages` exists and can be used for health.

## Auto-Filled Assumptions

- AS-001: "Deep read" interpreted as full review of auth, config, env overrides, usage, and Kimi provider transport paths in the upstream repo. (confidence: 90%)

- AS-002: "Implementation language: Python CLI (typer) to align with Kimi CLI stack." (confidence: 88%)
