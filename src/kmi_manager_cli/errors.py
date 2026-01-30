from __future__ import annotations

from kmi_manager_cli.config import Config


def no_keys_message(config: Config) -> str:
    return (
        "No API keys found in _auths/.\n"
        f"Expected directory: {config.auths_dir}\n"
        "Add one or more auth files (*.env, *.toml, *.json) with KMI_API_KEY for rotation/proxy.\n"
        "Note: ~/.kimi/config.toml is used only for the current account health view."
    )


def remediation_message() -> str:
    return (
        "All keys are unavailable.\n"
        "Next steps:\n"
        "- Check _auths/ for valid KMI_API_KEY entries\n"
        "- Verify quotas via /usages\n"
        "- Wait for cooldown if keys were rate-limited\n"
        "- Disable auto-rotation if prohibited by your provider"
    )


def status_hint(status_code: int) -> str:
    if status_code in {401, 403}:
        return "blocked"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code <= 599:
        return "upstream_error"
    return "unknown"
