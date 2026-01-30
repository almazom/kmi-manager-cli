# Agent Protocol - State Management & Execution

> Reference from KICKOFF.md when needed
> This document provides detailed state update patterns

## State File: state.json

The `state.json` file tracks execution progress. Update it after EACH card.

### State Structure

```json
{
  "overall_status": "IN_PROGRESS|COMPLETE|FAILED",
  "started_at": "2026-01-29T11:14:26Z",
  "completed_at": null,
  "current_card": "01",
  "agent_session_id": "session_1738142066",
  "cards": {
    "01": {
      "status": "pending|in_progress|completed|failed",
      "title": "Config + CLI scaffold",
      "started_at": null,
      "completed_at": null,
      "execution_time_seconds": null,
      "error": null
    }
  },
  "execution_log": []
}
```

## State Update Patterns

### Pattern 1: Start Execution (First Run)

```bash
cat > state.json << 'EON'
{
  "overall_status": "IN_PROGRESS",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "current_card": "01",
  "agent_session_id": "session_$(date +%s)",
  "cards": {
    "01": { "status": "pending", "title": "Config + CLI scaffold" },
    "02": { "status": "pending", "title": "Key registry" },
    "03": { "status": "pending", "title": "Proxy routing" },
    "04": { "status": "pending", "title": "Manual rotation" },
    "05": { "status": "pending", "title": "Auto rotation" },
    "06": { "status": "pending", "title": "Health & usage" },
    "07": { "status": "pending", "title": "Trace window" },
    "08": { "status": "pending", "title": "Error handling + logging" },
    "09": { "status": "pending", "title": "Global install + help" },
    "10": { "status": "pending", "title": "Manual E2E" }
  },
  "execution_log": []
}
EON
```

### Pattern 2: Start a Card

```bash
jq '.cards.01.status = "in_progress" | .cards.01.started_at = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"' \
   state.json > state.json.tmp && mv state.json.tmp state.json

jq '.current_card = "01"' \
   state.json > state.json.tmp && mv state.json.tmp state.json
```

### Pattern 3: Complete a Card

```bash
jq '.cards.01.status = "completed" | .cards.01.completed_at = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"' \
   state.json > state.json.tmp && mv state.json.tmp state.json
```

### Pattern 4: Fail a Card

```bash
jq --arg error "Error description" \
   '.cards.01.status = "failed" | .cards.01.error = $error | .overall_status = "FAILED"' \
   state.json > state.json.tmp && mv state.json.tmp state.json
```

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
