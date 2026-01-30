# KMI Manager CLI - Trello Board

> Scrum Master: AI Agent | Sprint: Linear Execution
> Story Point Cap: 4 SP per card | Principle: KISS

## Execution Order

```
┌────────────────────────────────────────────────────────┐
│                     EXECUTION PIPELINE                 │
├────────────────────────────────────────────────────────┤
│                                                        │
│  SPRINT 1: Foundation                                  │
│  ┌─────┐   ┌─────┐   ┌─────┐                          │
│  │ 01  │ → │ 02  │ → │ 03  │                          │
│  │ 3SP │   │ 3SP │   │ 4SP │                          │
│  └─────┘   └─────┘   └─────┘                          │
│  Config    Registry  Proxy                             │
│                                                        │
│  SPRINT 2: Rotation                                    │
│  ┌─────┐   ┌─────┐   ┌─────┐                          │
│  │ 04  │ → │ 05  │ → │ 06  │                          │
│  │ 3SP │   │ 4SP │   │ 3SP │                          │
│  └─────┘   └─────┘   └─────┘                          │
│  Manual    Auto     Health                             │
│                                                        │
│  SPRINT 3: Observability                               │
│  ┌─────┐   ┌─────┐                                    │
│  │ 07  │ → │ 08  │                                    │
│  │ 4SP │   │ 3SP │                                    │
│  └─────┘   └─────┘                                    │
│  Trace     Errors                                     │
│                                                        │
│  SPRINT 4: Packaging                                  │
│  ┌─────┐   ┌─────┐                                    │
│  │ 09  │ → │ 10  │                                    │
│  │ 2SP │   │ 1SP │                                    │
│  └─────┘   └─────┘                                    │
│  Install   E2E                                        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

## Card Index

| Card | Title | SP | Depends On | Status |
|------|-------|----|-----------:|--------|
| [01](./01-kmi-config.md) | Config + CLI scaffold | 3 | - | TODO |
| [02](./02-kmi-key-registry.md) | Key registry + _auths loader | 3 | 01 | TODO |
| [03](./03-kmi-proxy.md) | Proxy routing + unique base path | 4 | 02 | TODO |
| [04](./04-kmi-manual-rotate.md) | Manual rotation + dashboard | 3 | 03 | TODO |
| [05](./05-kmi-auto-rotate.md) | Auto rotation engine | 4 | 04 | TODO |
| [06](./06-kmi-health-usage.md) | Health + usage scoring | 3 | 05 | TODO |
| [07](./07-kmi-trace.md) | Trace logs + TUI | 4 | 06 | TODO |
| [08](./08-kmi-errors-logging.md) | Error handling + logging | 3 | 07 | TODO |
| [09](./09-kmi-global-cli.md) | Global install + `kmi --help` | 2 | 08 | TODO |
| [10](./10-kmi-manual-e2e.md) | Manual E2E + docs | 1 | 09 | TODO |

## Sprint Summary

- Sprint 1: 10 SP
- Sprint 2: 10 SP
- Sprint 3: 7 SP
- Sprint 4: 3 SP

**Total Story Points: 30**

---

## Reference

- Kimi CLI upstream: https://github.com/MoonshotAI/kimi-cli.git
