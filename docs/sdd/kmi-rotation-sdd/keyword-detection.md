# KMI Manager CLI - Command Detection Spec

> Status: DRAFT | Last updated: 2026-01-29 11:14:26 MSK

## Purpose

Define exact CLI tokens/flags that trigger each KMI Manager CLI action.

## Detection Strategy

**Approach:** Exact token match on CLI argv. No fuzzy matching.

## Patterns (FINAL LIST)

**Total: 8 patterns** - Case-sensitive for flags, case-insensitive for subcommands

### Group 1: Rotation
1. `kmi --rotate`
2. `kmi rotate`
3. `kmi --auto_rotate`
4. `kmi rotate auto`

### Group 2: Observability
5. `kmi --trace`
6. `kmi trace`
7. `kmi --all`
8. `kmi health`

## Matching Rules (CONFIRMED)

- Case-sensitive flags: `--rotate`, `--auto_rotate`, `--trace`, `--all`
- Subcommands are case-insensitive: `rotate`, `trace`, `health`
- Reject unknown flags with help output

## Edge Cases

| Input | Expected | Reason |
|-------|----------|--------|
| `kmi --rotat` | error | unknown flag |
| `kmi rotate AUTO` | valid | subcommand case-insensitive |
| `kmi --trace --rotate` | error | mutually exclusive modes |

## Performance

- Parsing must complete < 5ms
- No network calls during argument parsing
