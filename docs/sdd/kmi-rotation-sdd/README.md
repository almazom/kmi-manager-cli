# KMI Manager CLI - SDD Requirements

> Status: READY FOR IMPLEMENTATION | All gaps filled

## Overview

This folder contains Spec-Driven Development (SDD) documentation for the KMI Manager CLI feature set: multi-key rotation, proxy routing, and traceability for Kimi CLI usage.

## Documents

| File | Description | Status |
|------|-------------|--------|
| [requirements.md](./requirements.md) | Functional requirements | READY |
| [ui-flow.md](./ui-flow.md) | User interaction flow | READY |
| [keyword-detection.md](./keyword-detection.md) | Command/flag detection spec | READY |
| [gaps.md](./gaps.md) | Open questions & gaps | READY |
| [manual-e2e-test.md](./manual-e2e-test.md) | Manual test checklist | READY |
| [COMPLETENESS_REPORT.md](./COMPLETENESS_REPORT.md) | Coverage self-check | READY |

## Pipeline Summary

```
User Input → Detection → Acknowledgment → Execute → Trace → Delivery
     ↓           ↓             ↓            ↓        ↓        ↓
  [CLI]     [Flags]      [Dashboard]     [Proxy]  [JSONL]  [TUI]
```

## Quick Reference

| Aspect | Decision |
|--------|----------|
| **Channel** | CLI (local terminal) |
| **Detection** | CLI flags/subcommands (exact token match) |
| **Required Fields** | KMI_AUTHS_DIR, KMI_PROXY_BASE_PATH, KMI_UPSTREAM_BASE_URL, KMI_STATE_DIR |
| **Execution** | Local proxy + per-request key selection + env overrides |
| **Delivery** | TUI dashboard + JSONL logs + stdout |
| **Config** | .env + _auths/ + ~/.kmi/state |

## Requirements vs Deliverables

| Requirement | Covered By |
|------------|------------|
| Global `kmi --help` | Card 01, Card 09 |
| Manual rotate | Card 04, Card 09 |
| Auto rotate | Card 05, Card 06 |
| Trace window | Card 07 |
| Proxy routing | Card 03, Card 05 |
| Key health | Card 02, Card 06 |
| Secrets in .env | Card 01 |
| Unique proxy base path | Card 03 |
| SLA/ToS compliance toggle | Card 05, Card 08 |

## Development Notes

- [ ] Dry-run enabled by default during implementation
- [ ] Follow existing patterns from Kimi CLI env overrides (KIMI_API_KEY, KIMI_BASE_URL)
- [ ] Location: src/kmi_manager_cli/

## Implementation

See [trello-cards/BOARD.md](./trello-cards/BOARD.md) for:
- 10 executable cards (30 SP total)
- Linear execution order
- Machine-friendly instructions
- Max 4 SP per card
