# Card 10: KMI Manager CLI - Manual E2E + docs

| Field | Value |
|-------|-------|
| **ID** | KMI-10 |
| **Story Points** | 1 |
| **Depends On** | 09 |
| **Sprint** | 4 |

## User Story

> As an operator, I want a repeatable manual E2E checklist to validate rotation and trace.

## Context

Read before starting:
- [manual-e2e-test.md](../manual-e2e-test.md)
- [requirements.md#7-traceability--confidence](../requirements.md)
- Upstream reference: https://github.com/MoonshotAI/kimi-cli.git

## Must Have

- [ ] Manual test steps for rotate/auto/trace
- [ ] Validation steps for confidence metric
- [ ] Known-good sample outputs

## Instructions

### Step 1: Finalize manual E2E doc

```bash
# Review doc and update if missing steps
cat ../manual-e2e-test.md
```

### Step 2: Add sample outputs

```text
# Add expected output snippets for rotate + trace
```

### Step 3: Verification

```bash
# Run manual checklist
# (no automated tests required here)
```

## Acceptance Criteria

- [ ] Manual E2E checklist complete
- [ ] Sample outputs documented
- [ ] All docs marked READY

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
