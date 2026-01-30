# KMI Manager CLI Implementation - AI Agent Kickoff

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🤖 AI AGENT INSTRUCTION                                                    ║
║                                                                              ║
║   Execute ALL 10 cards below in LINEAR order.                                ║
║   Update state.json after EACH card.                                         ║
║   Do NOT stop until all cards are "completed".                               ║
║                                                                              ║
║   START NOW. First action: Read state.json, find first pending card.         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

> **ENTRY POINT**: This is the ONLY file you need. Everything is linked from here.
> This file is SELF-CONTAINED. Do not ask for clarification - all info is here.

## Mission

Implement the KMI Manager CLI feature by executing 10 Trello cards in linear order.
Track progress in `state.json`. Update after each step. Never skip cards.

**DRY-RUN MODE IS ON** - no API costs during development.

## Protocol

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT EXECUTION LOOP                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. READ state.json → Find current card (status = "pending")            │
│  2. UPDATE state.json → Set card to "in_progress"                       │
│  3. READ card file → Execute all instructions                           │
│  4. VERIFY → Check all acceptance criteria                              │
│  5. UPDATE state.json → Set card to "completed" or "failed"             │
│  6. UPDATE progress.md → Render progress bar                            │
│  7. LOOP → Go to step 1 until all cards completed                       │
│                                                                         │
│  ON ERROR: Set card to "failed", add error message, STOP for help        │
│  ON COMPLETE: Set overall status to "COMPLETE", celebrate 🎉            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose | Agent Action |
|------|---------|--------------|
| [BOARD.md](./BOARD.md) | Card overview and pipeline | Read once at start |
| [state.json](./state.json) | Progress tracking | Read+write each card |
| [AGENT_PROTOCOL.md](./AGENT_PROTOCOL.md) | State update patterns | Reference when needed |
| [01-*.md](./01-kmi-config.md) | First card | **Execute** |
| [02-*.md](./02-kmi-key-registry.md) | Second card | **Execute** |
| ... | ... | ... |
| [10-*.md](./10-kmi-manual-e2e.md) | Last card | **Execute** |

## Getting Started

```bash
cd trello-cards
ls -la
```

**First action:** Read [BOARD.md](./BOARD.md) to understand card sequence.

**Second action:** Read [state.json](./state.json) to find current card.

**Then:** Execute cards in order: 01 → 02 → 03 → ... → 10

## Completion Criteria

- [ ] All cards in state.json show "completed"
- [ ] No errors in execution log
- [ ] Manual E2E test passes (see card 10)
- [ ] Ready for production with `DRY_RUN=false`

## Troubleshooting

### If a command fails:

1. **Read the error message**
2. **Check file exists:** `ls -la path/to/file`
3. **Check syntax:** `cat file | head -20`
4. **Check dependencies:** Previous cards complete?
5. **Document error** in state.json
6. **Get help** if stuck >10 minutes

### If state.json is missing:

```bash
cat > state.json << 'EON'
{
  "overall_status": "IN_PROGRESS",
  "started_at": "2026-01-29T11:14:26Z",
  "current_card": "01",
  "agent_session_id": "session_1738142066",
  "cards": {
    "01": { "status": "pending", "started_at": null, "completed_at": null },
    "02": { "status": "pending", "started_at": null, "completed_at": null },
    "03": { "status": "pending", "started_at": null, "completed_at": null },
    "04": { "status": "pending", "started_at": null, "completed_at": null },
    "05": { "status": "pending", "started_at": null, "completed_at": null },
    "06": { "status": "pending", "started_at": null, "completed_at": null },
    "07": { "status": "pending", "started_at": null, "completed_at": null },
    "08": { "status": "pending", "started_at": null, "completed_at": null },
    "09": { "status": "pending", "started_at": null, "completed_at": null },
    "10": { "status": "pending", "started_at": null, "completed_at": null }
  },
  "execution_log": []
}
EON
```

## Success Definition

This implementation is **SUCCESSFUL** when:

1. ✅ All 10 cards completed
2. ✅ `kmi --help` works globally
3. ✅ Rotation, trace, and proxy routes working
4. ✅ Error handling + health metrics working
5. ✅ Manual E2E test passes

---

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
