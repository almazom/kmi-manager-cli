# Agent Rules (Priority Order)

1) **No sudo by default.** If a step needs sudo, stop and ask user explicitly.
2) **Proxy first.** Always ensure `kmi proxy` is running before testing `kimi` (background by default).
3) **Env correctness.** `KIMI_BASE_URL` must match proxy listen + base path.
4) **Prefer `kmi kimi` wrapper.** It forces proxy env regardless of shell state.
5) **Validate with trace.** A request is valid only when it appears in `~/.kmi/trace/trace.jsonl`.
6) **Doctor after changes.** Use `kmi doctor` as final check.
7) **Avoid destructive ops.** Never delete keys or state unless asked.
8) **Log everything.** If uncertain, capture outputs with `tail -n` + `rg`.
