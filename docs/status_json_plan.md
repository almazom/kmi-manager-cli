# Status JSON + Health Refresh Timestamp Plan

## Goals
- Provide `kmi status --json` for machine-readable status.
- Persist last health refresh time for easy visibility and diagnostics.
- Keep human-readable status output intact and easy to scan.

## Changes
1) Persist `last_health_refresh` in `state.json` on background health refresh.
2) Build a structured status payload and emit JSON when `--json` is used.
3) Update docs + schema to include the new field and command usage.
4) Add a CLI test for `kmi status --json`.

## Risks
- None on hot path: timestamp updates are background-only.
- Ensure JSON output has no extra lines (skip mode banner).

