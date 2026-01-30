# Project Context Notes

Last updated: 2026-01-29 11:14:26 MSK

## Local repo state

- Current repo has only SDD docs (no implementation code yet).
- Work will introduce a new CLI package under `src/kmi_manager_cli/`.

## Upstream Kimi CLI (cloned for reference)

Repo cloned to: `/tmp/tmp.aZ2UpCbylC/kimi-cli`

Key areas reviewed for auth/usage/transport behavior:
- `src/kimi_cli/config.py` (config + default paths)
- `src/kimi_cli/llm.py` (env overrides: `KIMI_API_KEY`, `KIMI_BASE_URL`)
- `src/kimi_cli/auth/oauth.py` (credential storage paths + device flow)
- `src/kimi_cli/ui/shell/usage.py` (usage endpoint `/usages`)
- `src/kimi_cli/auth/platforms.py` (platform base URLs)
- `packages/kosong/src/kosong/chat_provider/kimi.py` (OpenAI-style endpoints + base URL default)

Notes:
- Kimi CLI uses env overrides; wrapper can inject `KIMI_API_KEY` and `KIMI_BASE_URL` without editing config.
- Kimi provider uses OpenAI-style endpoints (e.g., `/chat/completions`).
- Usage endpoint exists and can be polled per key.
- Full repo file sweep executed (466 files, 24,770,406 bytes, 169,446 lines) to ensure complete coverage.

Reference repo:
- https://github.com/MoonshotAI/kimi-cli.git
